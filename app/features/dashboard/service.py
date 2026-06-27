from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Attempt, Exercise, FluencyReport, User

_AXES = [
    ("Understanding", "understanding_score"),
    ("Hypothesis", "hypothesis_score"),
    ("Prompting", "prompt_score"),
    ("Verification", "verification_score"),
    ("Testing", "testing_score"),
    ("Debugging", "debugging_score"),
]


async def build_dashboard(db: AsyncSession, user: User) -> dict:
    rows = (await db.execute(
        select(Attempt, FluencyReport, Exercise)
        .join(FluencyReport, FluencyReport.attempt_id == Attempt.id)
        .join(Exercise, Exercise.id == Attempt.exercise_id)
        .where(Attempt.user_id == user.id, Attempt.status == "scored")
        .order_by(Attempt.submitted_at.desc().nullslast(), Attempt.id.desc())
    )).all()

    completed = len(rows)
    avg_score = round(sum(r[0].score or 0 for r in rows) / completed, 1) if completed else 0.0

    radar = []
    for name, attr in _AXES:
        vals = [getattr(r[1], attr) for r in rows if getattr(r[1], attr) is not None]
        radar.append({"name": name, "value": round((sum(vals) / len(vals)) * 5, 1) if vals else 0.0})

    trend = [round(r[0].score or 0, 1) for r in reversed(rows)][-8:]

    recent = []
    for at, _rep, ex in rows[:6]:
        ok = (at.score or 0) >= 50
        recent.append({
            "title": ex.title,
            "meta": f"{ex.category}",
            "status": "PASSED" if ok else "REVIEW",
            "score": at.score,
            "ok": ok,
        })

    return {
        "kpis": {"completed": completed, "streak": min(completed, 30), "avg_score": avg_score},
        "radar": radar,
        "trend": trend or [0.0],
        "recent": recent,
    }
