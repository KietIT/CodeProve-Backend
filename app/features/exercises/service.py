from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Exercise, TestCase

_LEVEL_NAMES = {"fresher": "Fresher", "junior": "Junior", "senior": "Senior"}
_LEVEL_ORDER = ["fresher", "junior", "senior"]


def _topics(ex: Exercise) -> list[str]:
    return list(ex.domain_keywords or [ex.category])


async def list_grouped(db: AsyncSession, level: str | None) -> list[dict]:
    q = select(Exercise).order_by(Exercise.code)
    if level:
        q = q.where(Exercise.level == level)
    rows = (await db.execute(q)).scalars().all()
    groups: dict[str, list[dict]] = {}
    for ex in rows:
        groups.setdefault(ex.level, []).append({
            "id": ex.id, "code": ex.code, "title": ex.title, "difficulty": ex.difficulty,
            "acceptance": ex.acceptance, "topics": _topics(ex), "level": ex.level,
        })
    return [
        {"level": lv, "name": _LEVEL_NAMES.get(lv, lv.title()), "exercises": groups[lv]}
        for lv in _LEVEL_ORDER if lv in groups
    ]


async def get_detail(db: AsyncSession, code: str) -> dict | None:
    ex = (await db.execute(select(Exercise).where(Exercise.code == code.upper()))).scalar_one_or_none()
    if ex is None:
        return None
    tests = (await db.execute(
        select(TestCase).where(TestCase.exercise_id == ex.id).order_by(TestCase.order_index)
    )).scalars().all()
    return {
        "id": ex.id, "code": ex.code, "title": ex.title, "difficulty": ex.difficulty,
        "acceptance": ex.acceptance, "topics": _topics(ex), "level": ex.level,
        "summary": ex.summary, "language": ex.language, "starter": ex.starter_code,
        "hint": ex.hint, "tests": [t.description for t in tests],
    }
