import pytest
from datetime import date, datetime, timezone

from sqlalchemy import select

pytestmark = pytest.mark.asyncio


async def test_daily_challenge_round_trip(db_session):
    from app.models import DailyChallenge

    db_session.add(
        DailyChallenge(
            challenge_date=date(2026, 7, 4),
            prompt_title_vi="Kiểm tra một số có phải số nguyên tố",
            prompt_title_en="Check whether a number is prime",
            buggy_code="def is_prime(n):\n    return n > 1",
            buggy_line=2,
            bug_category="off-by-one",
            hint_1_vi="Xem lại điều kiện biên",
            hint_1_en="Look at the boundary condition",
            hint_2_vi="Số 4 có qua được không?",
            hint_2_en="Does 4 pass this check?",
            explanation_vi="Thiếu kiểm tra ước số, mọi n > 1 đều bị coi là nguyên tố.",
            explanation_en="The divisor check is missing, so every n > 1 counts as prime.",
        )
    )
    await db_session.commit()

    row = (
        await db_session.execute(
            select(DailyChallenge).where(DailyChallenge.challenge_date == date(2026, 7, 4))
        )
    ).scalar_one()
    assert row.prompt_title_vi == "Kiểm tra một số có phải số nguyên tố"
    assert row.prompt_title_en == "Check whether a number is prime"
    assert row.buggy_line == 2


async def test_daily_challenge_date_is_unique(db_session):
    from app.models import DailyChallenge
    from sqlalchemy.exc import IntegrityError

    db_session.add(
        DailyChallenge(
            challenge_date=date(2026, 7, 5), prompt_title_vi="a", prompt_title_en="a", buggy_code="x",
            buggy_line=1, bug_category="c", hint_1_vi="h1", hint_1_en="h1", hint_2_vi="h2", hint_2_en="h2",
            explanation_vi="e", explanation_en="e",
        )
    )
    await db_session.commit()
    db_session.add(
        DailyChallenge(
            challenge_date=date(2026, 7, 5), prompt_title_vi="b", prompt_title_en="b", buggy_code="y",
            buggy_line=1, bug_category="c", hint_1_vi="h1", hint_1_en="h1", hint_2_vi="h2", hint_2_en="h2",
            explanation_vi="e", explanation_en="e",
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_daily_attempt_unique_per_user_per_day(db_session):
    from app.models import DailyAttempt, User
    from sqlalchemy.exc import IntegrityError

    user = User(full_name="T", email="t@example.com", password_hash="x")
    db_session.add(user)
    await db_session.commit()

    db_session.add(DailyAttempt(user_id=user.id, challenge_date=date(2026, 7, 4)))
    await db_session.commit()
    db_session.add(DailyAttempt(user_id=user.id, challenge_date=date(2026, 7, 4)))
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_daily_attempt_submit_fields(db_session):
    from app.models import DailyAttempt, User

    user = User(full_name="T2", email="t2@example.com", password_hash="x")
    db_session.add(user)
    await db_session.commit()

    attempt = DailyAttempt(user_id=user.id, challenge_date=date(2026, 7, 4))
    db_session.add(attempt)
    await db_session.commit()
    attempt.selected_line = 2
    attempt.hints_used = 1
    attempt.time_taken_seconds = 45
    attempt.tier = "yellow"
    attempt.submitted_at = datetime.now(timezone.utc)
    await db_session.commit()

    row = (
        await db_session.execute(select(DailyAttempt).where(DailyAttempt.id == attempt.id))
    ).scalar_one()
    assert row.tier == "yellow"
    assert row.submitted_at is not None
