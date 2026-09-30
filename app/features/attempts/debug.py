"""The locate step of debug exercises (P2.2).

Before fixing, the student marks the buggy line(s) of the starter as served
(comments stripped) and says why, optionally after buying up to two hints.
Nothing is graded here: the location is recorded (LOCATE) and judged with the
rest of the session after submit, so it cannot be brute-forced; the answer is
revealed on the Feedback page.
"""
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.attempts import service
from app.features.exercises.debug_regions import hint_range
from app.features.exercises.starters import student_starter
from app.models import Attempt, Event, Exercise

MAX_HINTS = 2


def has_locate_step(ex: Exercise) -> bool:
    return ex.kind == "debug" and bool(ex.debug_meta)


def _served_line_count(ex: Exercise) -> int:
    return len(student_starter(ex.starter_code, "debug").split("\n"))


def hint_text(ex: Exercise, step: int, locale: str) -> str:
    meta = ex.debug_meta
    if step == 1:
        return meta["hint_vi"] if locale == "vi" else meta["hint_en"]
    lo, hi = hint_range(meta["regions"], _served_line_count(ex))
    return f"Xem kỹ các dòng {lo}–{hi}." if locale == "vi" else f"Look closely at lines {lo}–{hi}."


async def _logged(db: AsyncSession, attempt_id: int, type_: str) -> list[dict]:
    rows = (await db.execute(select(Event).where(Event.attempt_id == attempt_id, Event.type == type_)
                             .order_by(Event.id))).scalars().all()
    return [r.payload for r in rows]


async def state(db: AsyncSession, attempt: Attempt, ex: Exercise, locale: str) -> dict | None:
    """What a reload needs to restore the step; never the answer."""
    if not has_locate_step(ex):
        return None
    hints = await _logged(db, attempt.id, "DEBUG_HINT")
    return {"located": bool(await _logged(db, attempt.id, "LOCATE")), "hints_used": len(hints),
            "hints": [hint_text(ex, step, locale) for step in range(1, len(hints) + 1)]}


async def _open_step(db: AsyncSession, attempt: Attempt, ex: Exercise) -> int:
    """Checks the step is available; returns the hints already used."""
    if not has_locate_step(ex):
        raise HTTPException(status_code=400, detail="This exercise has no locate step")
    if attempt.status != "in_progress":
        raise HTTPException(status_code=409, detail="Attempt already submitted")
    if await _logged(db, attempt.id, "LOCATE"):
        raise HTTPException(status_code=409, detail="Bug already located")
    return len(await _logged(db, attempt.id, "DEBUG_HINT"))


async def take_hint(db: AsyncSession, attempt: Attempt, ex: Exercise, locale: str) -> dict:
    used = await _open_step(db, attempt, ex)
    if used >= MAX_HINTS:
        raise HTTPException(status_code=409, detail="No more hints")
    step = used + 1
    await service.add_event(db, attempt.id, "DEBUG_HINT", {"step": step})
    await db.commit()
    return {"step": step, "text": hint_text(ex, step, locale)}


async def locate(db: AsyncSession, attempt: Attempt, ex: Exercise, lines: list[int], reason: str,
                 skipped: bool) -> None:
    used = await _open_step(db, attempt, ex)
    if skipped:
        lines, reason = [], ""
    else:
        lines = sorted(set(lines))
        max_lines = len(ex.debug_meta["regions"]) + 1
        if not 1 <= len(lines) <= max_lines:
            raise HTTPException(status_code=422, detail=f"Select between 1 and {max_lines} lines")
        line_count = _served_line_count(ex)
        if any(not 1 <= line <= line_count for line in lines):
            raise HTTPException(status_code=422, detail=f"Lines must be between 1 and {line_count}")
        reason = reason.strip()
    await service.add_event(db, attempt.id, "LOCATE",
                            {"lines": lines, "reason": reason, "skipped": skipped, "hintsUsed": used})
    await db.commit()
