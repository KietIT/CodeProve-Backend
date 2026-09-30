"""Next-exercise recommendation from the learner model (P3.4).

Among the exercises the student has not solved, prefer those with a predicted
success near TARGET (Elo expectation of the student's mean rating over the
exercise's skills against its difficulty) that practise the student's weakest
skills. Lower score wins (approved 2026-09-30):

    |p - TARGET| - W_WEAK * weak_hits - W_DEBUG * [debug wanted and debug exercise]
                 + W_RECENT * [an unfinished attempt on it started < RECENT_HOURS ago]

Deterministic: ties go to the exercise code.
"""
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.content.skills import TAXONOMY
from app.features.learner import elo
from app.features.learner.brief import strong_and_weak
from app.features.learner.profile import SkillRating
from app.models import Attempt, Exercise, LearnerSkill

TARGET = 0.70
W_WEAK = 0.10
W_DEBUG = 0.10
W_RECENT = 0.30
RECENT_HOURS = 24
LIMIT = 3


class Recommendation(BaseModel):
    code: str
    title: str
    level: str
    kind: str
    skills: list[str]
    p: float  # predicted success; internal, never shown to students
    weak_skills: list[str]  # the student's weak skills this exercise practises


def rank(pool: list[Exercise], ratings: dict[str, float], weak: list[str], wants_debug: bool,
         recent_ids: set[int], limit: int = LIMIT) -> list[Recommendation]:
    scored: list[tuple[float, str, Recommendation]] = []
    for ex in pool:
        tags = list(ex.skills or [])
        mean = sum(ratings.get(t, elo.START_RATING) for t in tags) / len(tags) if tags else elo.START_RATING
        p = elo.expected(mean, elo.difficulty(ex.difficulty_elo, ex.level))
        hits = [t for t in tags if t in weak]
        kind = ex.kind or "implement"
        score = (abs(p - TARGET) - W_WEAK * len(hits) - W_DEBUG * (wants_debug and kind == "debug")
                 + W_RECENT * (ex.id in recent_ids))
        scored.append((score, ex.code, Recommendation(code=ex.code, title=ex.title, level=ex.level, kind=kind,
                                                      skills=tags, p=round(p, 3), weak_skills=hits)))
    scored.sort(key=lambda item: (item[0], item[1]))
    return [rec for _, _, rec in scored[:limit]]


def _utc(moment: datetime) -> datetime:
    # SQLite gives naive datetimes (stored as UTC); Postgres gives aware ones.
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


async def recommend(db: AsyncSession, user_id: int, *, current: Exercise | None = None,
                    levels: set[str] | None = None, wants_debug: bool = False,
                    limit: int = LIMIT) -> list[Recommendation]:
    attempts = (await db.execute(
        select(Attempt.exercise_id, Attempt.status, Attempt.started_at).where(Attempt.user_id == user_id)
    )).all()
    solved = {ex_id for ex_id, status, _ in attempts if status == "scored"}
    cutoff = datetime.now(timezone.utc) - timedelta(hours=RECENT_HOURS)
    recent = {ex_id for ex_id, status, started in attempts
              if status != "scored" and started is not None and _utc(started) >= cutoff}

    query = select(Exercise)
    if levels is not None:
        query = query.where(Exercise.level.in_(levels))
    pool = [ex for ex in (await db.execute(query)).scalars()
            if ex.id not in solved and (current is None or ex.id != current.id)]

    rows = (await db.execute(select(LearnerSkill).where(LearnerSkill.user_id == user_id))).scalars().all()
    ratings = {r.skill: r.rating for r in rows}
    skills = [SkillRating(key=r.skill, rating=r.rating, attempts=r.attempts, **TAXONOMY[r.skill])
              for r in rows if r.skill in TAXONOMY]
    _, weak = strong_and_weak(skills)
    return rank(pool, ratings, [s.key for s in weak], wants_debug, recent, limit)
