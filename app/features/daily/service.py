from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.daily.content import generate_challenge
from app.features.daily.streak import compute_streak
from app.models import DailyAttempt, DailyChallenge

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def today_vn() -> date:
    return datetime.now(VN_TZ).date()


async def get_or_create_challenge(db: AsyncSession, challenge_date: date) -> DailyChallenge:
    existing = (
        await db.execute(select(DailyChallenge).where(DailyChallenge.challenge_date == challenge_date))
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    try:
        return await generate_challenge(db, challenge_date)
    except IntegrityError:
        # Two simultaneous first-visitors-of-the-day both tried to generate;
        # the loser just reads back what the winner committed.
        await db.rollback()
        return (
            await db.execute(select(DailyChallenge).where(DailyChallenge.challenge_date == challenge_date))
        ).scalar_one()


async def challenge_number(db: AsyncSession, challenge_date: date) -> int:
    return (
        await db.execute(
            select(func.count()).select_from(DailyChallenge)
            .where(DailyChallenge.challenge_date <= challenge_date)
        )
    ).scalar_one()


async def get_attempt(db: AsyncSession, user_id: int, challenge_date: date) -> DailyAttempt | None:
    return (
        await db.execute(
            select(DailyAttempt).where(
                DailyAttempt.user_id == user_id, DailyAttempt.challenge_date == challenge_date
            )
        )
    ).scalar_one_or_none()


async def user_streak(db: AsyncSession, user_id: int, today: date) -> int:
    rows = (
        await db.execute(
            select(DailyAttempt.challenge_date).where(
                DailyAttempt.user_id == user_id, DailyAttempt.submitted_at.is_not(None)
            )
        )
    ).scalars().all()
    return compute_streak(set(rows), today)


def tier_for(correct: bool, hints_used: int, time_taken_seconds: int) -> str:
    if not correct:
        return "red"
    if hints_used == 0 and time_taken_seconds < 60:
        return "green"
    return "yellow"


async def submit_attempt(
    db: AsyncSession,
    user_id: int | None,
    selected_line: int,
    hints_used: int,
    time_taken_seconds: int,
) -> dict:
    today = today_vn()
    challenge = await get_or_create_challenge(db, today)
    correct = selected_line == challenge.buggy_line
    tier = tier_for(correct, hints_used, time_taken_seconds)

    streak: int | None = None
    if user_id is not None:
        attempt = await get_attempt(db, user_id, today)
        if attempt is None:
            attempt = DailyAttempt(user_id=user_id, challenge_date=today)
            db.add(attempt)
        attempt.selected_line = selected_line
        attempt.hints_used = hints_used
        attempt.time_taken_seconds = time_taken_seconds
        attempt.tier = tier
        attempt.submitted_at = datetime.now(timezone.utc)
        await db.commit()
        streak = await user_streak(db, user_id, today)

    return {
        "correct": correct,
        "tier": tier,
        "buggy_line": challenge.buggy_line,
        "explanation": challenge.explanation,
        "streak": streak,
    }
