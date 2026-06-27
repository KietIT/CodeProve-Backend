from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user
from app.features.attempts import service
from app.models import CodeSnapshot, Exercise, User
from app.schemas.attempt import AttemptOut, AttemptState, CreateAttemptIn, SnapshotIn
from app.schemas.event import EventsIn

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
