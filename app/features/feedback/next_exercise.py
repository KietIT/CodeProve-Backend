"""Which exercises feedback may suggest next (P1.5, ranked by the learner model since P3.4).

Deterministic, so the LLM writer can only pick from this list: exercises the
student has not solved, at the same level or one above (so a senior exercise
never leads back to fresher ones), ranked by learner.recommend (predicted
success near 0.70, weak skills, debug exercises after a debugging problem).
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.exercises.service import LEVEL_ORDER
from app.features.feedback.diagnosis import Finding
from app.features.learner.recommend import recommend
from app.models import Exercise

MAX_CANDIDATES = 3
_DEBUG_RISKS = {"bug_not_fixed", "partial_fix", "trial_and_error"}


def _rank(level: str) -> int:
    return LEVEL_ORDER.index(level) if level in LEVEL_ORDER else 0


async def candidates(db: AsyncSession, user_id: int, exercise: Exercise, findings: list[Finding]) -> list[str]:
    current = _rank(exercise.level)
    levels = set(LEVEL_ORDER[current:current + 2])
    wants_debug = any(f.code in _DEBUG_RISKS for f in findings)
    ranked = await recommend(db, user_id, current=exercise, levels=levels, wants_debug=wants_debug,
                             limit=MAX_CANDIDATES)
    return [r.code for r in ranked]
