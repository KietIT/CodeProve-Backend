import time

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Attempt, CodeSnapshot, Event, Exercise, User


def now_ms() -> int:
    return int(time.time() * 1000)


async def require_attempt(db: AsyncSession, attempt_id: int, user: User) -> Attempt:
    attempt = (await db.execute(select(Attempt).where(Attempt.id == attempt_id))).scalar_one_or_none()
    if attempt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found")
    if attempt.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your attempt")
    return attempt


async def add_event(db: AsyncSession, attempt_id: int, type_: str,
                    payload: dict | None = None, ts: int | None = None,
                    flags: list[str] | None = None) -> Event:
    event = Event(attempt_id=attempt_id, type=type_, ts=ts or now_ms(),
                  payload=payload or {}, integrity_flags=flags or [])
    db.add(event)
    return event


async def create_attempt(db: AsyncSession, user: User, exercise_code: str) -> Attempt:
    ex = (await db.execute(select(Exercise).where(Exercise.code == exercise_code.upper()))).scalar_one_or_none()
    if ex is None:
        raise HTTPException(status_code=404, detail="Exercise not found")
    attempt = Attempt(user_id=user.id, exercise_id=ex.id, status="in_progress")
    db.add(attempt)
    await db.flush()
    await add_event(db, attempt.id, "OPEN", {"exercise_code": ex.code})
    await db.commit()
    await db.refresh(attempt)
    return attempt


async def latest_code(db: AsyncSession, attempt_id: int) -> str | None:
    row = (await db.execute(
        select(CodeSnapshot).where(CodeSnapshot.attempt_id == attempt_id).order_by(CodeSnapshot.version.desc())
    )).scalars().first()
    return row.source_code if row else None
