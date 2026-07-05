import pytest
from datetime import date

pytestmark = pytest.mark.asyncio


class FakeJudgeClient:
    _model = "fake"
    calls = 0

    async def judge(self, system, user):
        FakeJudgeClient.calls += 1
        return {
            "buggy_code": "def f():\n    return 1",
            "buggy_line": 2,
            "bug_category": "off-by-one",
            "hint_1": "h1",
            "hint_2": "h2",
            "explanation": "e",
        }


@pytest.fixture(autouse=True)
def _patch_mentor_client(monkeypatch):
    import app.features.daily.content as content_mod

    FakeJudgeClient.calls = 0
    monkeypatch.setattr(content_mod, "get_mentor_client", lambda: FakeJudgeClient())


async def _make_user(db_session, email="svc@example.com"):
    from app.models import User

    user = User(full_name="Svc", email=email, password_hash="x")
    db_session.add(user)
    await db_session.commit()
    return user


async def test_today_vn_returns_a_date():
    from app.features.daily.service import today_vn

    assert isinstance(today_vn(), date)


async def test_get_or_create_challenge_returns_the_same_row_on_repeat_calls(db_session):
    from app.features.daily.service import get_or_create_challenge

    d = date(2026, 7, 4)
    first = await get_or_create_challenge(db_session, d)
    second = await get_or_create_challenge(db_session, d)
    assert first.id == second.id


async def test_get_or_create_challenge_calls_generation_only_once(db_session, monkeypatch):
    import app.features.daily.content as content_mod
    from app.features.daily.service import get_or_create_challenge

    calls = {"n": 0}
    original = content_mod.generate_challenge

    async def _counting(db, challenge_date):
        calls["n"] += 1
        return await original(db, challenge_date)

    monkeypatch.setattr("app.features.daily.service.generate_challenge", _counting)
    d = date(2026, 7, 5)
    await get_or_create_challenge(db_session, d)
    await get_or_create_challenge(db_session, d)
    assert calls["n"] == 1


async def test_challenge_number_counts_up_to_date(db_session):
    from app.features.daily.service import get_or_create_challenge, challenge_number

    await get_or_create_challenge(db_session, date(2026, 7, 1))
    await get_or_create_challenge(db_session, date(2026, 7, 2))
    await get_or_create_challenge(db_session, date(2026, 7, 3))
    assert await challenge_number(db_session, date(2026, 7, 2)) == 2
    assert await challenge_number(db_session, date(2026, 7, 3)) == 3


async def test_tier_for_green_requires_no_hints_and_under_60s():
    from app.features.daily.service import tier_for

    assert tier_for(correct=True, hints_used=0, time_taken_seconds=59) == "green"


async def test_tier_for_yellow_with_hint_or_slow():
    from app.features.daily.service import tier_for

    assert tier_for(correct=True, hints_used=1, time_taken_seconds=10) == "yellow"
    assert tier_for(correct=True, hints_used=0, time_taken_seconds=61) == "yellow"


async def test_tier_for_red_when_incorrect():
    from app.features.daily.service import tier_for

    assert tier_for(correct=False, hints_used=0, time_taken_seconds=5) == "red"


async def test_submit_attempt_persists_for_logged_in_user_and_returns_streak(db_session):
    # submit_attempt resolves "today" itself via today_vn() - the test must
    # anchor on that same value rather than a hardcoded date, or this becomes
    # a test that only passes when run on one specific calendar day.
    from app.features.daily.service import get_or_create_challenge, submit_attempt, today_vn

    d = today_vn()
    challenge = await get_or_create_challenge(db_session, d)
    user = await _make_user(db_session)

    result = await submit_attempt(
        db_session, user.id, selected_line=challenge.buggy_line, hints_used=0, time_taken_seconds=30
    )
    assert result["correct"] is True
    assert result["tier"] == "green"
    assert result["buggy_line"] == challenge.buggy_line
    assert result["streak"] == 1


async def test_submit_attempt_anonymous_does_not_persist_and_streak_is_none(db_session):
    from app.features.daily.service import get_or_create_challenge, submit_attempt, today_vn
    from app.models import DailyAttempt
    from sqlalchemy import select

    d = today_vn()
    challenge = await get_or_create_challenge(db_session, d)

    result = await submit_attempt(
        db_session, None, selected_line=challenge.buggy_line, hints_used=0, time_taken_seconds=10
    )
    assert result["streak"] is None
    rows = (await db_session.execute(select(DailyAttempt))).scalars().all()
    assert rows == []
