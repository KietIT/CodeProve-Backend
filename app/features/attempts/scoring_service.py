from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.attempts import service as attempts_service
from app.features.mentor.client import get_mentor_client
from app.features.mentor.prompts import EXPLAIN_QUESTION_SYSTEM, EXPLAIN_SCORE_SYSTEM
from app.features.scoring.engine import score_attempt
from app.features.scoring.features import AxisFeatures
from app.models import Attempt, CodeSnapshot, Event, Exercise, FluencyReport, VerificationAnswer

_AXIS_LABELS = {
    "understanding": "Understanding",
    "hypothesis": "Hypothesis",
    "prompting": "Prompting",
    "verification": "Verification",
    "testing": "Testing",
    "debugging": "Debugging",
}


def tier_for(overall: float) -> str:
    if overall >= 85:
        return "Exceptional"
    if overall >= 70:
        return "Strong"
    if overall >= 50:
        return "Developing"
    return "Emerging"


def integrity_from_features(f: AxisFeatures) -> str:
    if f.integrity_flag_total >= 4:
        return "red"
    if f.integrity_flag_total >= 1:
        return "yellow"
    return "green"


def build_feedback(axes: dict, f: AxisFeatures) -> dict:
    strengths, risks, per_axis = [], [], {}
    for axis, score in axes.items():
        if score is None:
            continue
        notes = []
        if score >= 16:
            strengths.append({"axis": _AXIS_LABELS[axis], "note": f"Strong {_AXIS_LABELS[axis].lower()}."})
            notes.append("Above target.")
        elif score < 10:
            risks.append({"axis": _AXIS_LABELS[axis], "note": f"Improve your {_AXIS_LABELS[axis].lower()}."})
            notes.append("Below target.")
        per_axis[axis] = {"score": score, "notes": notes}
    if f.has_v1b:
        risks.append({"axis": "Verification", "note": "You accepted AI code containing a bug without checking it."})
    if f.p1_hits:
        risks.append({"axis": "Prompting", "note": "Some prompts were too short to be effective."})
    return {"strengths": strengths[:4], "risks": risks[:4], "per_axis": per_axis}


def build_timeline(f: AxisFeatures) -> list[dict]:
    return [
        {
            "step": "Step 1 · Hypothesis",
            "title": "Approach logged before coding",
            "desc": (
                "A hypothesis was recorded before the first code edit."
                if f.has_hypothesis_before_code
                else "No hypothesis was logged before coding."
            ),
            "active": f.has_hypothesis_before_code,
        },
        {
            "step": "Step 2 · Implementation",
            "title": "Solution ran against tests",
            "desc": f"Best coverage {int(f.best_coverage * 100)}%." if f.has_test_run else "No tests were run.",
            "active": f.has_test_run,
        },
        {
            "step": "Step 3 · Explain-back",
            "title": "Reasoning verified",
            "desc": f"Explanation scored {f.explain_score:.0f}/20.",
            "active": f.explain_score >= 10,
        },
    ]


async def _events_as_dicts(db: AsyncSession, attempt_id: int) -> list[dict]:
    rows = (
        await db.execute(
            select(Event).where(Event.attempt_id == attempt_id).order_by(Event.ts)
        )
    ).scalars().all()
    return [
        {"type": r.type, "ts": r.ts, "payload": r.payload or {}, "integrity_flags": r.integrity_flags or []}
        for r in rows
    ]


async def generate_questions(db: AsyncSession, attempt: Attempt) -> list[str]:
    ex = (await db.execute(select(Exercise).where(Exercise.id == attempt.exercise_id))).scalar_one()
    code = (
        await db.execute(
            select(CodeSnapshot)
            .where(CodeSnapshot.attempt_id == attempt.id)
            .order_by(CodeSnapshot.version.desc())
        )
    ).scalars().first()
    src = code.source_code if code else "(no code submitted)"
    out = await get_mentor_client().judge(
        EXPLAIN_QUESTION_SYSTEM,
        f"Problem: {ex.summary}\nStudent code:\n{src}",
    )
    questions = out.get("questions") or ["Explain in your own words why your solution is correct."]
    return questions[:2]


async def score_with_explanations(db: AsyncSession, attempt: Attempt, answers: list[dict]) -> dict:
    client = get_mentor_client()
    scores = []
    for a in answers:
        verdict = await client.judge(
            EXPLAIN_SCORE_SYSTEM,
            f"Question: {a['question']}\nAnswer: {a['answer']}",
        )
        s = float(verdict.get("score", 0))
        scores.append(max(0.0, min(20.0, s)))
        db.add(VerificationAnswer(attempt_id=attempt.id, question=a["question"], answer=a["answer"], score=s))

    explain_score = sum(scores) / len(scores) if scores else 0.0
    await attempts_service.add_event(db, attempt.id, "EXPLAIN_BACK", {"explainScore": explain_score})

    events = await _events_as_dicts(db, attempt.id)
    result = score_attempt(events, explain_score=explain_score)
    axes = result["axes"]
    f = result["features"]
    integrity = integrity_from_features(f)

    feedback_with_timeline = {**build_feedback(axes, f), "timeline": build_timeline(f)}

    report = FluencyReport(
        attempt_id=attempt.id,
        understanding_score=axes["understanding"],
        hypothesis_score=axes["hypothesis"],
        prompt_score=axes["prompting"],
        verification_score=axes["verification"],
        testing_score=axes["testing"],
        debugging_score=axes["debugging"],
        explanation_score=explain_score,
        overall_score=result["overall"],
        feedback=feedback_with_timeline,
    )
    db.add(report)
    attempt.score = result["overall"]
    attempt.status = "scored"
    attempt.integrity_status = integrity
    await db.commit()

    return _report_payload(axes, result["overall"], f, integrity)


def _report_payload(axes: dict, overall: float, f: AxisFeatures, integrity: str) -> dict:
    axes_pct = {a: (v * 5 if v is not None else None) for a, v in axes.items()}
    return {
        "overall": overall,
        "tier": tier_for(overall),
        "axes": axes,
        "axes_pct": axes_pct,
        "feedback": build_feedback(axes, f),
        "integrity_status": integrity,
        "timeline": build_timeline(f),
    }
