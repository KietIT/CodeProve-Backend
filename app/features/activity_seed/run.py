"""Seed practice history (3-5 scored attempts a day since signup) for learners who agreed to it.

Emails come on stdin, one per line, so they never land in the repo or the shell history:

    docker exec -i codeprove_backend python -m app.features.activity_seed.run < emails.txt           # dry run
    docker exec -i codeprove_backend python -m app.features.activity_seed.run --apply < emails.txt   # write

Every seeded report carries feedback["seed_batch"] (default "seed-<today>"). Rescore, the learner
difficulty Elo, rater sampling and the Free monthly submit quota all skip seeded attempts.
Undo a batch (all learners, or only the emails given on stdin):

    docker exec -i codeprove_backend python -m app.features.activity_seed.run --rollback seed-2026-11-23 --apply < /dev/null

Both --apply runs finish with a learner-model rebuild, so skill ratings match the reports.
"""
import argparse
import asyncio
import random
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import async_session_maker
from app.features.activity_seed.marker import SEED_KEY, seed_batch_of
from app.features.activity_seed.plan import ExerciseInfo, Interval, PlannedAttempt, not_applicable, plan_learner
from app.features.attempts.scoring_service import build_feedback
from app.features.learner.service import rebuild
from app.features.scoring.features import AxisFeatures
from app.models import Attempt, CodeSnapshot, Event, Exercise, FluencyReport, User

DEFAULT_SEED = 20261123
ASSUMED_ATTEMPT = timedelta(minutes=30)  # busy time for an existing attempt that was never submitted


def read_emails(lines: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    for line in lines:
        email = line.strip().lower()
        if email and not email.startswith("#"):
            seen[email] = None
    return list(seen)


async def _seeded_attempt_ids(db: AsyncSession, batch: str, user_ids: list[int] | None) -> list[int]:
    query = select(FluencyReport.attempt_id, FluencyReport.feedback).join(Attempt, Attempt.id == FluencyReport.attempt_id)
    if user_ids is not None:
        query = query.where(Attempt.user_id.in_(user_ids))
    return [aid for aid, feedback in (await db.execute(query)).all() if seed_batch_of(feedback) == batch]


async def _history(db: AsyncSession, user_id: int) -> tuple[dict[int, int], list[Interval]]:
    """(scored attempts per exercise, busy intervals) of the learner's existing attempts."""
    attempts = (await db.execute(select(Attempt).where(Attempt.user_id == user_id))).scalars().all()
    done = Counter(a.exercise_id for a in attempts if a.status == "scored")
    busy = [(a.started_at, a.submitted_at or a.started_at + ASSUMED_ATTEMPT) for a in attempts]
    return dict(done), [(_utc(s), _utc(e)) for s, e in busy]


def _utc(value: datetime) -> datetime:
    # SQLite (tests) returns naive datetimes; Postgres returns aware ones.
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _feedback(planned: PlannedAttempt, batch: str) -> dict:
    na = not_applicable(planned.axes)
    return {**build_feedback(planned.axes, AxisFeatures(), na), "timeline": [], SEED_KEY: batch}


def _store(db: AsyncSession, user_id: int, planned: PlannedAttempt) -> Attempt:
    attempt = Attempt(user_id=user_id, exercise_id=planned.exercise_id, score=planned.overall, status="scored",
                      integrity_status=planned.integrity, started_at=planned.started_at,
                      submitted_at=planned.submitted_at, created_at=planned.started_at)
    db.add(attempt)
    return attempt


async def seed(db: AsyncSession, emails: list[str], batch: str, seed_value: int, now: datetime,
               apply: bool) -> dict[str, list[PlannedAttempt]]:
    users = {u.email: u for u in (await db.execute(
        select(User).where(User.email.in_(emails), User.role == "user"))).scalars()}
    missing = [e for e in emails if e not in users]
    if missing:
        raise SystemExit(f"No learner account for: {', '.join(missing)}")
    already = await _seeded_attempt_ids(db, batch, [u.id for u in users.values()])
    if already:
        raise SystemExit(f"Batch {batch!r} already has {len(already)} attempt(s) for these learners; "
                         f"roll it back first or pass another --batch")
    exercises = {ex.id: ex for ex in (await db.execute(select(Exercise))).scalars()}
    if not exercises:
        raise SystemExit("No exercises in the database")
    infos = [ExerciseInfo(ex.id, ex.level, ex.difficulty, ex.kind) for ex in exercises.values()]

    plans: dict[str, list[PlannedAttempt]] = {}
    for email in emails:
        user = users[email]
        done, busy = await _history(db, user.id)
        rng = random.Random(f"{seed_value}:{email}")
        plans[email] = plan_learner(rng, _utc(user.created_at), now, infos, done, busy)
    if not apply:
        return plans

    for email, planned_list in plans.items():
        for planned in planned_list:
            exercise = exercises[planned.exercise_id]
            attempt = _store(db, users[email].id, planned)
            await db.flush()
            db.add(FluencyReport(
                attempt_id=attempt.id, understanding_score=planned.axes["understanding"],
                hypothesis_score=planned.axes["hypothesis"], prompt_score=planned.axes["prompting"],
                verification_score=planned.axes["verification"], testing_score=planned.axes["testing"],
                debugging_score=planned.axes["debugging"], explanation_score=planned.explanation,
                overall_score=planned.overall, feedback=_feedback(planned, batch), created_at=planned.submitted_at,
            ))
            db.add(CodeSnapshot(attempt_id=attempt.id, version=1,
                                source_code=exercise.reference_solution or exercise.starter_code or "",
                                created_at=planned.submitted_at))
    await db.commit()
    await rebuild(db, apply=True)
    return plans


async def rollback(db: AsyncSession, batch: str, emails: list[str], apply: bool) -> int:
    user_ids = None
    if emails:
        user_ids = list((await db.execute(select(User.id).where(User.email.in_(emails)))).scalars())
    ids = await _seeded_attempt_ids(db, batch, user_ids)
    if apply and ids:
        # Explicit child deletes: SQLite (tests) does not cascade without the FK pragma.
        for model in (CodeSnapshot, FluencyReport, Event):
            await db.execute(delete(model).where(model.attempt_id.in_(ids)))
        await db.execute(delete(Attempt).where(Attempt.id.in_(ids)))
        await db.commit()
        await rebuild(db, apply=True)
    return len(ids)


def _summary(plans: dict[str, list[PlannedAttempt]]) -> None:
    total = 0
    for email, planned in plans.items():
        total += len(planned)
        if not planned:
            print(f"{email:<40} nothing to add")
            continue
        days = Counter(p.started_at.date() for p in planned)
        avg = sum(p.overall for p in planned) / len(planned)
        print(f"{email:<40} {len(planned):>4} attempts over {len(days):>3} day(s), "
              f"{min(days.values())}-{max(days.values())}/day, avg {avg:5.1f}, "
              f"{planned[0].started_at:%Y-%m-%d} -> {planned[-1].started_at:%Y-%m-%d}")
    print(f"total {total} attempt(s)")


async def _main(args: argparse.Namespace) -> int:
    emails = read_emails(sys.stdin.readlines())
    async with async_session_maker() as db:
        if args.rollback:
            count = await rollback(db, args.rollback, emails, args.apply)
            verb = "deleted" if args.apply else "would delete (dry run, use --apply)"
            print(f"{count} seeded attempt(s) of batch {args.rollback!r} {verb}")
            return 0
        if not emails:
            print("No emails on stdin")
            return 2
        plans = await seed(db, emails, args.batch, args.seed, datetime.now(timezone.utc), args.apply)
    _summary(plans)
    print(f"batch {args.batch!r}: " + ("written, learner model rebuilt" if args.apply else "dry run, use --apply to write"))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="write (default: dry run)")
    parser.add_argument("--batch", default=f"seed-{datetime.now(timezone.utc):%Y-%m-%d}", help="marker for rollback")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="RNG seed; same seed = same plan")
    parser.add_argument("--rollback", metavar="BATCH", help="delete the attempts of this batch instead")
    sys.exit(asyncio.run(_main(parser.parse_args())))
