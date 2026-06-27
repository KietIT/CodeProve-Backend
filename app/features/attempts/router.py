from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.core.deps import get_current_user
from app.features.attempts import scoring_service, service
from app.features.sandbox.runner import run_tests as sandbox_run
from app.models import CodeSnapshot, Exercise, FluencyReport, TestCase, User
from app.schemas.attempt import AttemptOut, AttemptState, CreateAttemptIn, RunIn, RunResult, SnapshotIn
from app.schemas.event import EventsIn
from app.schemas.report import ExplainBackIn, ReportOut

router = APIRouter(prefix="/api/attempts", tags=["attempts"])


@router.post("", response_model=AttemptOut)
async def create(data: CreateAttemptIn, db: AsyncSession = Depends(get_db),
                 user: User = Depends(get_current_user)) -> AttemptOut:
    attempt = await service.create_attempt(db, user, data.exercise_code)
    return AttemptOut(attempt_id=attempt.id, started_at=attempt.started_at)


@router.get("/{attempt_id}", response_model=AttemptState)
async def get_state(attempt_id: int, db: AsyncSession = Depends(get_db),
                    user: User = Depends(get_current_user)) -> AttemptState:
    attempt = await service.require_attempt(db, attempt_id, user)
    ex = (await db.execute(select(Exercise).where(Exercise.id == attempt.exercise_id))).scalar_one()
    return AttemptState(id=attempt.id, exercise_code=ex.code, status=attempt.status,
                        score=attempt.score, latest_code=await service.latest_code(db, attempt.id))


@router.post("/{attempt_id}/events")
async def ingest_events(attempt_id: int, data: EventsIn, db: AsyncSession = Depends(get_db),
                        user: User = Depends(get_current_user)) -> dict:
    await service.require_attempt(db, attempt_id, user)
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
    attempt = await service.require_attempt(db, attempt_id, user)
    cases = (await db.execute(
        select(TestCase).where(TestCase.exercise_id == attempt.exercise_id).order_by(TestCase.order_index)
    )).scalars().all()
    case_dicts = [{"input_data": c.input_data, "expected_output": c.expected_output,
                   "description": c.description, "weight": c.weight} for c in cases]
    result = await sandbox_run(data.source_code, case_dicts, get_settings().sandbox_timeout)

    # snapshot + telemetry
    next_version = 1 + len((await db.execute(
        select(CodeSnapshot).where(CodeSnapshot.attempt_id == attempt_id))).scalars().all())
    db.add(CodeSnapshot(attempt_id=attempt_id, version=next_version, source_code=data.source_code))
    all_passed = result["total"] > 0 and result["passed"] == result["total"]
    await service.add_event(db, attempt_id, "RUN", {"passed": all_passed})
    if data.run_tests:
        await service.add_event(db, attempt_id, "TEST_RUN", {
            "passed": all_passed, "testCount": result["total"], "coverage": result["coverage"]})
    await db.commit()
    return RunResult(**result)


@router.post("/{attempt_id}/submit")
async def submit(
    attempt_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    attempt = await service.require_attempt(db, attempt_id, user)
    await service.add_event(db, attempt_id, "SUBMIT", {})
    attempt.status = "submitted"
    attempt.submitted_at = datetime.now(timezone.utc)
    questions = await scoring_service.generate_questions(db, attempt)
    await db.commit()
    return {"questions": questions}


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
