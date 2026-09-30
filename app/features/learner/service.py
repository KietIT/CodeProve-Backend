"""Keep the learner model up to date (P3.3).

`record_attempt` applies one scored attempt right after scoring; `rebuild`
replays every stored report in time order and must give the same result, so
the model can be recomputed after a rescore or a formula change.

Approved rules: every scored attempt moves the student, but an exercise's
difficulty only moves on each student's first scored attempt of it, and never
for the simulated calibration accounts.
"""
from dataclasses import dataclass

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.learner import elo
from app.models import Attempt, Exercise, FluencyReport, LearnerSkill, User


def is_sim_account(email: str) -> bool:
    # Accounts made by calibration.simulate: "calib.sim{:02d}@example.com".
    return email.startswith("calib.sim") and email.endswith("@example.com")


async def _is_first_scored(db: AsyncSession, attempt: Attempt) -> bool:
    earlier = (await db.execute(
        select(func.count()).select_from(Attempt)
        .where(Attempt.user_id == attempt.user_id, Attempt.exercise_id == attempt.exercise_id,
               Attempt.status == "scored", Attempt.id != attempt.id)
    )).scalar_one()
    return earlier == 0


async def record_attempt(db: AsyncSession, attempt: Attempt, exercise: Exercise, overall: float | None) -> None:
    """Apply one scored attempt. Reads first, then only sets attributes and adds rows,
    so a failure here leaves the session usable (the caller commits)."""
    tags = list(exercise.skills or [])
    if not tags:
        return
    rows = {r.skill: r for r in (await db.execute(
        select(LearnerSkill).where(LearnerSkill.user_id == attempt.user_id, LearnerSkill.skill.in_(tags))
    )).scalars()}
    email = (await db.execute(select(User.email).where(User.id == attempt.user_id))).scalar_one()
    move = not is_sim_account(email) and await _is_first_scored(db, attempt)

    current = {t: rows[t].rating if t in rows else elo.START_RATING for t in tags}
    ratings, difficulty = elo.update(current, elo.difficulty(exercise.difficulty_elo, exercise.level), overall, move)
    for tag, rating in ratings.items():
        if tag in rows:
            rows[tag].rating = rating
            rows[tag].attempts += 1
        else:
            db.add(LearnerSkill(user_id=attempt.user_id, skill=tag, rating=rating, attempts=1))
    if move:
        exercise.difficulty_elo = difficulty


@dataclass
class RebuildResult:
    reports: int
    students: int
    ratings: dict[tuple[int, str], tuple[float, int]]  # (user_id, skill) -> (rating, attempts)
    difficulties: dict[int, float]  # exercise_id -> difficulty


async def replay(db: AsyncSession) -> RebuildResult:
    """Recompute the whole model from the stored reports, oldest first."""
    exercises = {ex.id: ex for ex in (await db.execute(select(Exercise))).scalars()}
    rows = (await db.execute(
        select(FluencyReport.overall_score, Attempt.user_id, Attempt.exercise_id, User.email)
        .join(Attempt, Attempt.id == FluencyReport.attempt_id)
        .join(User, User.id == Attempt.user_id)
        .order_by(func.coalesce(Attempt.submitted_at, FluencyReport.created_at), FluencyReport.id)
    )).all()
    ratings: dict[tuple[int, str], tuple[float, int]] = {}
    difficulties: dict[int, float] = {}
    seen: set[tuple[int, int]] = set()
    for overall, user_id, exercise_id, email in rows:
        ex = exercises[exercise_id]
        tags = list(ex.skills or [])
        first = (user_id, exercise_id) not in seen
        seen.add((user_id, exercise_id))
        if not tags:
            continue
        current = {t: ratings.get((user_id, t), (elo.START_RATING, 0))[0] for t in tags}
        move = first and not is_sim_account(email)
        new, d = elo.update(current, elo.difficulty(difficulties.get(exercise_id), ex.level), overall, move)
        for tag, rating in new.items():
            ratings[(user_id, tag)] = (rating, ratings.get((user_id, tag), (0.0, 0))[1] + 1)
        if move:
            difficulties[exercise_id] = d
    return RebuildResult(reports=len(rows), students=len({u for u, _ in ratings}), ratings=ratings,
                         difficulties=difficulties)


async def rebuild(db: AsyncSession, apply: bool) -> RebuildResult:
    result = await replay(db)
    if apply:
        await db.execute(delete(LearnerSkill))
        for (user_id, skill), (rating, attempts) in result.ratings.items():
            db.add(LearnerSkill(user_id=user_id, skill=skill, rating=rating, attempts=attempts))
        for ex in (await db.execute(select(Exercise))).scalars():
            ex.difficulty_elo = result.difficulties.get(ex.id)
        await db.commit()
    return result
