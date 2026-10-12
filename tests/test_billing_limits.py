"""Plan-based limits: Ciel messages per day and submissions per month."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import select

import app.features.mentor.quota as quota_mod
from app.core.config import Settings
from app.models import Attempt, Exercise, PromptLog, Subscription, User


@pytest.fixture
def settings(monkeypatch):
    def use(**over):
        values = {"ciel_per_attempt": 100, "ciel_per_minute": 100, "ciel_per_day": 3, "ciel_per_day_plus": 5,
                  "ciel_per_day_pro": 7, "free_submits_per_month": 2, **over}
        monkeypatch.setattr(quota_mod, "get_settings", lambda: Settings(**values))
    return use


async def _user(db_session) -> User:
    return (await db_session.execute(select(User))).scalars().first()


async def _exercise(db_session) -> Exercise:
    ex = (await db_session.execute(select(Exercise))).scalars().first()
    if ex is None:
        ex = Exercise(code="CP-001", title="t", difficulty="Easy", category="c", level="junior", language="python",
                      summary="s", starter_code="x", hint="h", domain_keywords=[])
        db_session.add(ex)
        await db_session.flush()
    return ex


async def _attempt(db_session, user, *, submitted_at=None, status="in_progress") -> Attempt:
    ex = await _exercise(db_session)
    at = Attempt(user_id=user.id, exercise_id=ex.id, status=status, submitted_at=submitted_at)
    db_session.add(at)
    await db_session.commit()
    return at


async def _give(db_session, user, tier, days=30):
    db_session.add(Subscription(user_id=user.id, tier=tier, expires_at=datetime.now(timezone.utc) + timedelta(days=days)))
    await db_session.commit()


# --- submissions per month -----------------------------------------------------------------------

async def test_free_user_is_blocked_after_the_monthly_limit(client, db_session, auth_headers, settings):
    settings()
    user = await _user(db_session)
    now = datetime.now(timezone.utc)
    await _attempt(db_session, user, submitted_at=now, status="scored")
    await _attempt(db_session, user, submitted_at=now, status="scored")
    third = await _attempt(db_session, user)
    with pytest.raises(HTTPException) as err:
        await quota_mod.enforce_monthly_submits(db_session, user, third)
    assert err.value.status_code == 429
    detail = err.value.detail
    assert detail["code"] == "monthly_submit_limit" and detail["tier"] == "free" and detail["upgrade"] is True
    assert "2" in detail["message_vi"] and "2" in detail["message_en"]


async def test_free_user_under_the_limit_may_submit(client, db_session, auth_headers, settings):
    settings()
    user = await _user(db_session)
    await _attempt(db_session, user, submitted_at=datetime.now(timezone.utc), status="scored")
    second = await _attempt(db_session, user)
    await quota_mod.enforce_monthly_submits(db_session, user, second)  # one used of two: fine


async def test_last_months_submissions_do_not_count(client, db_session, auth_headers, settings):
    settings()
    user = await _user(db_session)
    old = quota_mod.month_start_utc() - timedelta(days=1)
    await _attempt(db_session, user, submitted_at=old, status="scored")
    await _attempt(db_session, user, submitted_at=old, status="scored")
    fresh = await _attempt(db_session, user)
    await quota_mod.enforce_monthly_submits(db_session, user, fresh)


async def test_resubmitting_the_same_attempt_is_not_counted_twice(client, db_session, auth_headers, settings):
    settings(free_submits_per_month=1)
    user = await _user(db_session)
    mine = await _attempt(db_session, user, submitted_at=datetime.now(timezone.utc), status="submitted")
    await quota_mod.enforce_monthly_submits(db_session, user, mine)


async def test_other_users_submissions_do_not_count(client, db_session, auth_headers, settings):
    settings(free_submits_per_month=1)
    user = await _user(db_session)
    other = User(full_name="O", email="o@example.com", password_hash="x")
    db_session.add(other)
    await db_session.flush()
    await _attempt(db_session, other, submitted_at=datetime.now(timezone.utc), status="scored")
    mine = await _attempt(db_session, user)
    await quota_mod.enforce_monthly_submits(db_session, user, mine)


@pytest.mark.parametrize("tier", ["plus", "pro"])
async def test_paid_plans_have_no_monthly_limit(client, db_session, auth_headers, settings, tier):
    settings(free_submits_per_month=1)
    user = await _user(db_session)
    await _give(db_session, user, tier)
    for _ in range(3):
        await _attempt(db_session, user, submitted_at=datetime.now(timezone.utc), status="scored")
    nxt = await _attempt(db_session, user)
    await quota_mod.enforce_monthly_submits(db_session, user, nxt)


async def test_expired_paid_plan_is_limited_again(client, db_session, auth_headers, settings):
    settings(free_submits_per_month=1)
    user = await _user(db_session)
    await _give(db_session, user, "plus", days=-1)
    await _attempt(db_session, user, submitted_at=datetime.now(timezone.utc), status="scored")
    nxt = await _attempt(db_session, user)
    with pytest.raises(HTTPException):
        await quota_mod.enforce_monthly_submits(db_session, user, nxt)


async def test_submit_endpoint_answers_429_when_over_the_free_limit(client, db_session, auth_headers, settings):
    settings(free_submits_per_month=1)
    user = await _user(db_session)
    await _attempt(db_session, user, submitted_at=datetime.now(timezone.utc), status="scored")
    ex = await _exercise(db_session)
    aid = (await client.post("/api/attempts", json={"exercise_code": ex.code}, headers=auth_headers)).json()["attempt_id"]
    r = await client.post(f"/api/attempts/{aid}/submit", headers=auth_headers)
    assert r.status_code == 429 and r.json()["detail"]["code"] == "monthly_submit_limit"


# --- Ciel messages per day -----------------------------------------------------------------------

async def test_ciel_daily_cap_depends_on_the_plan(client, db_session, auth_headers, settings):
    settings()
    user = await _user(db_session)
    at = await _attempt(db_session, user)
    assert (await quota_mod.ciel_left(db_session, user.id, at.id)).day_left == 3
    await _give(db_session, user, "plus")
    assert (await quota_mod.ciel_left(db_session, user.id, at.id)).day_left == 5
    sub = (await db_session.execute(select(Subscription))).scalars().first()
    sub.tier = "pro"
    await db_session.commit()
    assert (await quota_mod.ciel_left(db_session, user.id, at.id)).day_left == 7


async def test_free_user_hits_the_daily_cap_and_is_offered_an_upgrade(client, db_session, auth_headers, settings):
    settings(ciel_per_day=1)
    user = await _user(db_session)
    at = await _attempt(db_session, user)
    db_session.add(PromptLog(attempt_id=at.id, prompt="hi", response="hello"))
    await db_session.commit()
    with pytest.raises(HTTPException) as err:
        await quota_mod.enforce_ciel(db_session, user, at)
    assert err.value.detail["code"] == "ciel_daily_limit" and err.value.detail["upgrade"] is True


async def test_pro_user_hitting_the_cap_gets_no_upgrade_offer(client, db_session, auth_headers, settings):
    settings(ciel_per_day_pro=1)
    user = await _user(db_session)
    await _give(db_session, user, "pro")
    at = await _attempt(db_session, user)
    db_session.add(PromptLog(attempt_id=at.id, prompt="hi", response="hello"))
    await db_session.commit()
    with pytest.raises(HTTPException) as err:
        await quota_mod.enforce_ciel(db_session, user, at)
    assert err.value.detail["tier"] == "pro" and err.value.detail["upgrade"] is False


def test_entitlements_follow_the_settings():
    from app.features.billing import entitlements

    s = Settings(ciel_per_day=1, ciel_per_day_plus=2, ciel_per_day_pro=3, free_submits_per_month=4)
    got = [entitlements.for_tier(t, s) for t in ("free", "plus", "pro")]
    assert [e.ciel_per_day for e in got] == [1, 2, 3]
    assert [e.monthly_submits for e in got] == [4, None, None]
