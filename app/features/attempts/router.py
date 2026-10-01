from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import rate_limit
from app.core.config import get_settings
from app.core.db import get_db
from app.core.deps import get_current_user
from app.features.attempts import debug, scoring_service, service, submit_tests
from app.features.exercises.starters import is_untouched, student_starter
from app.features.mentor.quota import ciel_left
from app.features.sandbox.runner import run_tests as sandbox_run
from app.models import CodeSnapshot, Exercise, FluencyReport, TestCase, User
from app.features.student_tests import service as student_tests
from app.features.student_tests.evaluate import evaluate as evaluate_student_tests
from app.schemas.attempt import (
    AttemptOut, AttemptState, CheckOut, CreateAttemptIn, HintOut, LocateIn, OwnRunIn, RunIn, RunResult, SnapshotIn,
    StudentTestIn, StudentTestsIn,
)
from app.schemas.event import EventsIn
from app.schemas.report import ExplainBackIn, ReportOut

router = APIRouter(prefix="/api/attempts", tags=["attempts"])


@router.post("", response_model=AttemptOut)
async def create(data: CreateAttemptIn, db: AsyncSession = Depends(get_db),
                 user: User = Depends(get_current_user)) -> AttemptOut:
    attempt = await service.create_attempt(db, user, data.exercise_code)
    return AttemptOut(attempt_id=attempt.id, started_at=attempt.started_at)


@router.get("/{attempt_id}", response_model=AttemptState)
async def get_state(attempt_id: int, locale: str = "en", db: AsyncSession = Depends(get_db),
                    user: User = Depends(get_current_user)) -> AttemptState:
    attempt = await service.require_attempt(db, attempt_id, user)
    ex = (await db.execute(select(Exercise).where(Exercise.id == attempt.exercise_id))).scalar_one()
    return AttemptState(id=attempt.id, exercise_code=ex.code, status=attempt.status,
                        score=attempt.score, latest_code=await service.latest_code(db, attempt.id),
                        debug=await debug.state(db, attempt, ex, locale),
                        tests=await student_tests.state(db, attempt, ex),
                        ciel=await ciel_left(db, user.id, attempt.id))


async def _attempt_and_exercise(db: AsyncSession, attempt_id: int, user: User):
    attempt = await service.require_attempt(db, attempt_id, user)
    ex = (await db.execute(select(Exercise).where(Exercise.id == attempt.exercise_id))).scalar_one()
    return attempt, ex


@router.put("/{attempt_id}/tests")
async def save_tests(attempt_id: int, data: StudentTestsIn, db: AsyncSession = Depends(get_db),
                     user: User = Depends(get_current_user)) -> dict:
    attempt, ex = await _attempt_and_exercise(db, attempt_id, user)
    await student_tests.save(db, attempt, ex, [t.model_dump() for t in data.tests])
    return {"ok": True}


@router.post("/{attempt_id}/tests/check", response_model=CheckOut)
async def check_test(attempt_id: int, data: StudentTestIn, db: AsyncSession = Depends(get_db),
                     user: User = Depends(get_current_user)) -> CheckOut:
    settings = get_settings()
    rate_limit.enforce(f"sandbox:{user.id}", settings.sandbox_rate_limit_per_minute, 60)
    attempt, ex = await _attempt_and_exercise(db, attempt_id, user)
    return CheckOut(**await student_tests.check(db, attempt, ex, data.model_dump()))


@router.post("/{attempt_id}/tests/run")
async def run_student_tests(attempt_id: int, data: OwnRunIn, db: AsyncSession = Depends(get_db),
                            user: User = Depends(get_current_user)) -> dict:
    settings = get_settings()
    rate_limit.enforce(f"sandbox:{user.id}", settings.sandbox_rate_limit_per_minute, 60)
    attempt, ex = await _attempt_and_exercise(db, attempt_id, user)
    return {"results": await student_tests.run_on_own_code(db, attempt, ex, data.source_code)}


@router.post("/{attempt_id}/debug/hint", response_model=HintOut)
async def debug_hint(attempt_id: int, locale: str = "en", db: AsyncSession = Depends(get_db),
                     user: User = Depends(get_current_user)) -> HintOut:
    attempt = await service.require_attempt(db, attempt_id, user)
    ex = (await db.execute(select(Exercise).where(Exercise.id == attempt.exercise_id))).scalar_one()
    return HintOut(**await debug.take_hint(db, attempt, ex, locale))


@router.post("/{attempt_id}/debug/locate")
async def debug_locate(attempt_id: int, data: LocateIn, db: AsyncSession = Depends(get_db),
                       user: User = Depends(get_current_user)) -> dict:
    attempt = await service.require_attempt(db, attempt_id, user)
    ex = (await db.execute(select(Exercise).where(Exercise.id == attempt.exercise_id))).scalar_one()
    await debug.locate(db, attempt, ex, data.lines, data.reason, data.skipped)
    return {"ok": True}


@router.post("/{attempt_id}/events")
async def ingest_events(attempt_id: int, data: EventsIn, db: AsyncSession = Depends(get_db),
                        user: User = Depends(get_current_user)) -> dict:
    await service.require_attempt(db, attempt_id, user)
    forged = sorted({e.type for e in data.events} & service.SERVER_EVENT_TYPES)
    if forged:
        raise HTTPException(status_code=422, detail=f"Server-owned event types cannot be sent: {', '.join(forged)}")
    for e in data.events:
        await service.add_event(db, attempt_id, e.type, e.payload, e.ts, e.integrity_flags)
    await db.commit()
    return {"ingested": len(data.events)}


@router.post("/{attempt_id}/snapshots")
async def add_snapshot(attempt_id: int, data: SnapshotIn, db: AsyncSession = Depends(get_db),
                       user: User = Depends(get_current_user)) -> dict:
    await service.require_attempt(db, attempt_id, user)
    db.add(CodeSnapshot(attempt_id=attempt_id, version=data.version, source_code=data.source_code))
    await db.commit()
    return {"ok": True}


@router.post("/{attempt_id}/run", response_model=RunResult)
async def run(attempt_id: int, data: RunIn, db: AsyncSession = Depends(get_db),
              user: User = Depends(get_current_user)) -> RunResult:
    settings = get_settings()
    rate_limit.enforce(f"sandbox:{user.id}", settings.sandbox_rate_limit_per_minute, 60)
    attempt = await service.require_attempt(db, attempt_id, user)
    ex = (await db.execute(select(Exercise).where(Exercise.id == attempt.exercise_id))).scalar_one()
    # Hidden tests only run at submit (P1.2); never expose their names or results here.
    cases = (await db.execute(
        select(TestCase).where(TestCase.exercise_id == attempt.exercise_id, TestCase.is_hidden.is_(False))
        .order_by(TestCase.order_index)
    )).scalars().all()
    case_dicts = [{"input_data": c.input_data, "expected_output": c.expected_output,
                   "description": c.description, "weight": c.weight} for c in cases]
    result = await sandbox_run(data.source_code, case_dicts, settings.sandbox_timeout)

    # snapshot + telemetry
    next_version = 1 + len((await db.execute(
        select(CodeSnapshot).where(CodeSnapshot.attempt_id == attempt_id))).scalars().all())
    db.add(CodeSnapshot(attempt_id=attempt_id, version=next_version, source_code=data.source_code))
    all_passed = result["total"] > 0 and result["passed"] == result["total"]
    pass_ratio = round(result["passed"] / result["total"], 3) if result["total"] else 0.0
    # isStarter: running the untouched scaffold (or an empty editor) is not a real
    # attempt, so scoring must not count its failure as something "debugged".
    await service.add_event(db, attempt_id, "RUN", {
        "passed": all_passed,
        "passRatio": pass_ratio,
        "isStarter": is_untouched(data.source_code, student_starter(ex.starter_code, ex.kind)),
    })
    if data.run_tests:
        await service.add_event(db, attempt_id, "TEST_RUN", {
            "passed": all_passed, "testCount": result["total"], "coverage": result["coverage"]})
    await db.commit()
    return RunResult(**result)


@router.post("/{attempt_id}/submit")
async def submit(
    attempt_id: int,
    locale: str = "en",
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    attempt = await service.require_attempt(db, attempt_id, user)
    if attempt.status == "scored":
        raise HTTPException(status_code=409, detail="Attempt already scored")
    settings = get_settings()
    rate_limit.enforce(f"sandbox:{user.id}", settings.sandbox_rate_limit_per_minute, 60)
    suite = await submit_tests.run_submit_suite(db, attempt)
    ex = (await db.execute(select(Exercise).where(Exercise.id == attempt.exercise_id))).scalar_one()
    await evaluate_student_tests(db, attempt, ex)
    # The report's feedback is written in the language the student submitted in.
    await service.add_event(db, attempt_id, "SUBMIT", {"locale": "vi" if locale == "vi" else "en"})
    attempt.status = "submitted"
    attempt.submitted_at = datetime.now(timezone.utc)
    questions = await scoring_service.generate_questions(db, attempt, locale)
    await db.commit()
    return {"questions": questions, "tests": submit_tests.public_summary(suite)}


@router.post("/{attempt_id}/explain-back", response_model=ReportOut)
async def explain_back(
    attempt_id: int,
    data: ExplainBackIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ReportOut:
    attempt = await service.require_attempt(db, attempt_id, user)
    if attempt.status == "scored":
        raise HTTPException(status_code=409, detail="Attempt already scored")
    payload = await scoring_service.score_with_explanations(
        db, attempt, [a.model_dump() for a in data.answers]
    )
    return ReportOut(**payload)


@router.get("/{attempt_id}/report", response_model=ReportOut)
async def report(
    attempt_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ReportOut:
    attempt = await service.require_attempt(db, attempt_id, user)
    rep = (
        await db.execute(select(FluencyReport).where(FluencyReport.attempt_id == attempt_id))
    ).scalar_one_or_none()
    if rep is None:
        raise HTTPException(status_code=404, detail="No report yet")
    axes = {
        "understanding": rep.understanding_score,
        "hypothesis": rep.hypothesis_score,
        "prompting": rep.prompt_score,
        "verification": rep.verification_score,
        "testing": rep.testing_score,
        "debugging": rep.debugging_score,
    }
    axes_pct = {a: (v * 5 if v is not None else None) for a, v in axes.items()}
    stored = rep.feedback if isinstance(rep.feedback, dict) else {}
    timeline = stored.get("timeline", [])
    # Return feedback without the embedded timeline so the shape matches the
    # explain-back response (timeline is exposed only at the top level).
    feedback = {k: v for k, v in stored.items() if k != "timeline"}
    return ReportOut(
        overall=rep.overall_score,
        tier=scoring_service.tier_for(rep.overall_score),
        axes=axes,
        axes_pct=axes_pct,
        feedback=feedback,
        integrity_status=attempt.integrity_status or "green",
        timeline=timeline,
    )
