"""Per-student caps on LLM calls (P3.6).

Counted from the database (prompt_logs, HYPOTHESIS events), so they survive
restarts and hold with several workers; the per-minute burst cap uses the
in-memory limiter. One student message is one prompt_logs row, whatever the
guard retried.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import rate_limit
from app.core.config import get_settings
from app.models import Attempt, Event, PromptLog, User
from app.schemas.mentor import CielQuota

MESSAGES = {
    "ciel_attempt_limit": ("Bạn đã dùng hết {n} tin nhắn với Ciel cho lượt làm bài này.",
                           "You have used all {n} Ciel messages for this attempt."),
    "ciel_daily_limit": ("Bạn đã dùng hết {n} tin nhắn với Ciel hôm nay. Hãy quay lại vào ngày mai.",
                         "You have used all {n} Ciel messages for today. Please come back tomorrow."),
    "hypothesis_limit": ("Bạn đã kiểm tra giả thuyết {n} lần trong lượt làm bài này.",
                         "You have checked your hypothesis {n} times in this attempt."),
    "rate_limited": ("Bạn gửi hơi nhanh. Hãy đợi một chút rồi thử lại.",
                     "You are sending too fast. Please wait a moment and try again."),
}


def _limit_error(code: str, n: int, retry_after: int | None = None) -> HTTPException:
    vi, en = MESSAGES[code]
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail={"code": code, "message_vi": vi.format(n=n), "message_en": en.format(n=n)},
        headers={"Retry-After": str(retry_after)} if retry_after else None,
    )


def day_start_utc(now: datetime | None = None) -> datetime:
    """Midnight of today in the quota time zone, as UTC."""
    tz = ZoneInfo(get_settings().quota_timezone)
    local = (now or datetime.now(timezone.utc)).astimezone(tz)
    return local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)


async def ciel_left(db: AsyncSession, user_id: int, attempt_id: int) -> CielQuota:
    s = get_settings()
    in_attempt = (await db.execute(
        select(func.count()).select_from(PromptLog).where(PromptLog.attempt_id == attempt_id))).scalar_one()
    today = (await db.execute(
        select(func.count()).select_from(PromptLog).join(Attempt, Attempt.id == PromptLog.attempt_id)
        .where(Attempt.user_id == user_id, PromptLog.created_at >= day_start_utc()))).scalar_one()
    return CielQuota(attempt_left=max(s.ciel_per_attempt - in_attempt, 0), day_left=max(s.ciel_per_day - today, 0))


async def enforce_ciel(db: AsyncSession, user: User, attempt: Attempt) -> None:
    s = get_settings()
    left = await ciel_left(db, user.id, attempt.id)
    if left.attempt_left == 0:
        raise _limit_error("ciel_attempt_limit", s.ciel_per_attempt)
    if left.day_left == 0:
        raise _limit_error("ciel_daily_limit", s.ciel_per_day)
    # Last, so a refused message does not use up the burst allowance.
    retry_after = rate_limit.hit(f"ciel:{user.id}", s.ciel_per_minute, 60)
    if retry_after > 0:
        raise _limit_error("rate_limited", s.ciel_per_minute, max(1, int(retry_after) + 1))


async def enforce_hypothesis(db: AsyncSession, attempt: Attempt) -> None:
    n = get_settings().hypothesis_per_attempt
    used = (await db.execute(select(func.count()).select_from(Event).where(
        Event.attempt_id == attempt.id, Event.type == "HYPOTHESIS"))).scalar_one()
    if used >= n:
        raise _limit_error("hypothesis_limit", n)
