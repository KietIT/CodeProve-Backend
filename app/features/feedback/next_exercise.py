"""Which exercises feedback may suggest next (P1.5).

Deterministic, so the LLM writer can only pick from this list: exercises the
student has not solved, at the same level or one above, preferring the same
category, and debug exercises when the session showed a debugging problem.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.exercises.service import LEVEL_ORDER, status_by_exercise
from app.features.feedback.diagnosis import Finding
from app.models import Exercise

MAX_CANDIDATES = 3
_DEBUG_RISKS = {"bug_not_fixed", "partial_fix", "trial_and_error"}


def _rank(level: str) -> int:
    return LEVEL_ORDER.index(level) if level in LEVEL_ORDER else 0


async def candidates(db: AsyncSession, user_id: int, exercise: Exercise, findings: list[Finding]) -> list[str]:
    current = _rank(exercise.level)
    allowed = set(LEVEL_ORDER[current:current + 2])
    wants_debug = any(f.code in _DEBUG_RISKS for f in findings)
    solved = {ex_id for ex_id, status in (await status_by_exercise(db, user_id)).items() if status == "solved"}
    pool = [
        ex for ex in (await db.execute(select(Exercise).where(Exercise.level.in_(allowed)))).scalars()
        if ex.id != exercise.id and ex.id not in solved
    ]
    pool.sort(key=lambda ex: (
        wants_debug and (ex.kind or "implement") != "debug",  # debugging problems: debug exercises first
        ex.category != exercise.category,
        _rank(ex.level) - current,
        ex.code,
    ))
    return [ex.code for ex in pool[:MAX_CANDIDATES]]
