from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Attempt, Exercise, TestCase

_LEVEL_NAMES = {"fresher": "Fresher", "junior": "Junior", "senior": "Senior"}
_LEVEL_ORDER = ["fresher", "junior", "senior"]


def _topics(ex: Exercise) -> list[str]:
    return list(ex.domain_keywords or [ex.category])


async def _status_by_exercise(db: AsyncSession, user_id: int) -> dict[int, str]:
    """Map exercise_id -> "solved" | "attempted" for the given user.

    "solved" wins over "attempted" and mirrors the dashboard: an exercise counts
    as solved once any attempt on it reaches status "scored".
    """
    rows = (
        await db.execute(
            select(Attempt.exercise_id, Attempt.status).where(Attempt.user_id == user_id)
        )
    ).all()
    status: dict[int, str] = {}
    for ex_id, st in rows:
        if st == "scored":
            status[ex_id] = "solved"
        elif status.get(ex_id) != "solved":
            status[ex_id] = "attempted"
    return status


async def list_grouped(db: AsyncSession, level: str | None, user_id: int | None = None) -> list[dict]:
    q = select(Exercise).order_by(Exercise.code)
    if level:
        q = q.where(Exercise.level == level)
    rows = (await db.execute(q)).scalars().all()
    status_map = await _status_by_exercise(db, user_id) if user_id is not None else {}
    groups: dict[str, list[Exercise]] = {}
    for ex in rows:
        groups.setdefault(ex.level, []).append(ex)
    result = []
    for lv in _LEVEL_ORDER:
        if lv not in groups:
            continue
        # Rows are ordered by code, so the 1-based position is the display number.
        exercises = [
            {
                "id": ex.id, "num": i, "code": ex.code, "title": ex.title,
                "difficulty": ex.difficulty, "acceptance": ex.acceptance,
                "topics": _topics(ex), "level": ex.level,
                "status": status_map.get(ex.id, "todo"),
            }
            for i, ex in enumerate(groups[lv], start=1)
        ]
        result.append({"level": lv, "name": _LEVEL_NAMES.get(lv, lv.title()), "exercises": exercises})
    return result


async def get_detail(db: AsyncSession, code: str) -> dict | None:
    ex = (await db.execute(select(Exercise).where(Exercise.code == code.upper()))).scalar_one_or_none()
    if ex is None:
        return None
    tests = (await db.execute(
        select(TestCase).where(TestCase.exercise_id == ex.id).order_by(TestCase.order_index)
    )).scalars().all()
    # Display number = 1-based position within the level (codes sort numerically here).
    num = (await db.execute(
        select(func.count()).select_from(Exercise)
        .where(Exercise.level == ex.level, Exercise.code <= ex.code)
    )).scalar_one()
    return {
        "id": ex.id, "num": num, "code": ex.code, "title": ex.title, "difficulty": ex.difficulty,
        "acceptance": ex.acceptance, "topics": _topics(ex), "level": ex.level,
        "summary": ex.summary, "language": ex.language, "starter": ex.starter_code,
        "hint": ex.hint, "tests": [t.description for t in tests],
    }
