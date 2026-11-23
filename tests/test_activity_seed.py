"""Seeded practice history: plan shape, write/rollback, and that seeded attempts stay out of calibration and quota."""
import random
from collections import Counter
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.features.activity_seed import run
from app.features.activity_seed.marker import SEED_KEY, is_seeded
from app.features.activity_seed.plan import DAY_END, DAY_START, LOCAL_TZ, ExerciseInfo, plan_learner
from app.features.learner.service import replay
from app.features.mentor.quota import enforce_monthly_submits
from app.features.scoring.rescore import rescore_all
from app.models import Attempt, CodeSnapshot, Exercise, FluencyReport, User

NOW = datetime(2026, 11, 23, 15, 0, tzinfo=timezone.utc)  # 22:00 in Vietnam
EXERCISES = [ExerciseInfo(i, lvl, diff, kind) for i, (lvl, diff, kind) in enumerate([
    ("fresher", "Easy", "implement"), ("fresher", "Easy", "debug"), ("junior", "Medium", "implement"),
    ("junior", "Medium", "debug"), ("senior", "Hard", "implement"), ("fresher", "Medium", "implement"),
], start=1)]


def test_plan_has_three_to_five_attempts_each_full_day_inside_waking_hours():
    signup = datetime(2026, 11, 13, 2, 0, tzinfo=timezone.utc)  # 09:00 local
    planned = plan_learner(random.Random(1), signup, NOW, EXERCISES)
    per_day = Counter(p.started_at.astimezone(LOCAL_TZ).date() for p in planned)
    assert len(per_day) == 11  # 13/11 .. 23/11
    assert all(3 <= n <= 5 for n in per_day.values())
    spans = sorted((p.started_at, p.submitted_at) for p in planned)
    for start, end in spans:
        local_start, local_end = start.astimezone(LOCAL_TZ), end.astimezone(LOCAL_TZ)
        assert start > signup and end < NOW and start < end
        assert DAY_START <= local_start.time() and local_end.time() <= DAY_END
    assert all(a[1] <= b[0] for a, b in zip(spans, spans[1:]))  # no overlap
    assert all(0 <= p.overall <= 100 for p in planned)


def test_plan_avoids_existing_attempts_and_late_signup_day():
    signup = datetime(2026, 11, 22, 16, 20, tzinfo=timezone.utc)  # 23:20 local: no room that day
    busy = [(datetime(2026, 11, 23, 0, 0, tzinfo=timezone.utc), datetime(2026, 11, 23, 15, 0, tzinfo=timezone.utc))]
    planned = plan_learner(random.Random(2), signup, NOW, EXERCISES, busy=busy)
    assert all(p.started_at.astimezone(LOCAL_TZ).date().day == 23 for p in planned)
    assert all(p.submitted_at <= busy[0][0] for p in planned)


async def _setup(db):
    users = []
    for i, email in enumerate(("a@x.vn", "b@x.vn")):
        u = User(full_name=email, email=email, password_hash="x", created_at=NOW - timedelta(days=5 + i))
        db.add(u)
        users.append(u)
    for info in EXERCISES:
        db.add(Exercise(id=info.id, code=f"CP-{info.id:03d}", title="t", difficulty=info.difficulty, category="c",
                        level=info.level, kind=info.kind, language="python", summary="s", starter_code="def f(): pass",
                        hint="h", domain_keywords=[], skills=["hash-map"]))
    await db.commit()
    return users


@pytest.mark.asyncio
async def test_seed_writes_marked_scored_attempts_and_rollback_removes_them(db_session):
    users = await _setup(db_session)
    dry = await run.seed(db_session, ["a@x.vn", "b@x.vn"], "seed-t", 7, NOW, apply=False)
    assert (await db_session.scalar(select(func.count(Attempt.id)))) == 0
    plans = await run.seed(db_session, ["a@x.vn", "b@x.vn"], "seed-t", 7, NOW, apply=True)
    assert {e: len(p) for e, p in plans.items()} == {e: len(p) for e, p in dry.items()}

    total = sum(len(p) for p in plans.values())
    attempts = (await db_session.execute(select(Attempt))).scalars().all()
    assert len(attempts) == total and all(a.status == "scored" for a in attempts)
    reports = (await db_session.execute(select(FluencyReport))).scalars().all()
    assert len(reports) == total and all(r.feedback[SEED_KEY] == "seed-t" for r in reports)
    assert (await db_session.scalar(select(func.count(CodeSnapshot.id)))) == total
    assert {a.user_id for a in attempts} == {u.id for u in users}

    with pytest.raises(SystemExit):  # same batch twice
        await run.seed(db_session, ["a@x.vn"], "seed-t", 7, NOW, apply=True)

    assert await run.rollback(db_session, "seed-t", ["a@x.vn"], apply=True) == len(plans["a@x.vn"])
    assert await run.rollback(db_session, "seed-t", [], apply=True) == len(plans["b@x.vn"])
    assert (await db_session.scalar(select(func.count(Attempt.id)))) == 0


@pytest.mark.asyncio
async def test_seed_rejects_unknown_email(db_session):
    await _setup(db_session)
    with pytest.raises(SystemExit):
        await run.seed(db_session, ["nobody@x.vn"], "seed-t", 7, NOW, apply=False)


@pytest.mark.asyncio
async def test_seeded_attempts_skip_difficulty_rescore_and_quota(db_session):
    users = await _setup(db_session)
    await run.seed(db_session, ["a@x.vn"], "seed-t", 7, NOW, apply=True)

    result = await replay(db_session)
    assert result.difficulties == {}  # seeded attempts never calibrate an exercise
    assert any(uid == users[0].id for uid, _ in result.ratings)  # but the learner's skills move

    assert await rescore_all(db_session, apply=True) == []
    scores = [r.feedback for r in (await db_session.execute(select(FluencyReport))).scalars()]
    assert all(is_seeded(f) and "rescored_from" not in f for f in scores)

    # Free plan: seeded submissions this month do not use up the real quota.
    fresh = Attempt(user_id=users[0].id, exercise_id=1, status="in_progress")
    db_session.add(fresh)
    await db_session.commit()
    await enforce_monthly_submits(db_session, users[0], fresh)


@pytest.mark.asyncio
async def test_seed_since_starts_no_earlier_than_that_day(db_session):
    await _setup(db_session)  # signups 5 and 6 days before NOW
    since = run._local_day("2026-11-21")
    plans = await run.seed(db_session, ["a@x.vn", "b@x.vn"], "seed-t", 7, NOW, apply=False, since=since)
    days = {p.started_at.astimezone(LOCAL_TZ).date().day for planned in plans.values() for p in planned}
    assert days == {21, 22, 23}
