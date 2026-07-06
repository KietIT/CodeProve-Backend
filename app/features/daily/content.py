import random
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.daily.prompts_bank import DAILY_PROMPTS
from app.features.mentor.client import get_mentor_client
from app.features.mentor.prompts import DAILY_CHALLENGE_SYSTEM
from app.models import DailyChallenge

_LOOKBACK_DAYS = 30
# Bilingual hints + explanations roughly double the completion text, so the
# budget sits well above the shared judge() default of 300.
_JUDGE_MAX_TOKENS = 1500


class DailyGenerationError(Exception):
    """Raised when the LLM response for a daily challenge is missing or unusable.

    Prevents committing a garbage DailyChallenge row (e.g. from a truncated
    or empty JSON response) that would otherwise be locked in for the day.
    """


async def _recent_titles(db: AsyncSession, before: date) -> set[str]:
    """English titles used in the last 30 days - the stable exclusion key."""
    cutoff = before - timedelta(days=_LOOKBACK_DAYS)
    rows = (
        await db.execute(
            select(DailyChallenge.prompt_title_en).where(
                DailyChallenge.challenge_date >= cutoff, DailyChallenge.challenge_date < before
            )
        )
    ).scalars().all()
    return set(rows)


def _pick_prompt(exclude: set[str]) -> dict[str, str]:
    available = [p for p in DAILY_PROMPTS if p["en"] not in exclude]
    # If the whole bank was used in the last 30 days, allow a repeat rather
    # than fail the day's challenge.
    pool = available or DAILY_PROMPTS
    return random.choice(pool)


async def generate_challenge(db: AsyncSession, challenge_date: date) -> DailyChallenge:
    """Pick an unused prompt title and ask Ciel to write a buggy solution for it."""
    exclude = await _recent_titles(db, challenge_date)
    prompt = _pick_prompt(exclude)
    data = await get_mentor_client().judge(
        DAILY_CHALLENGE_SYSTEM, f"Problem title: {prompt['en']}", max_tokens=_JUDGE_MAX_TOKENS
    )

    buggy_code = data.get("buggy_code") or ""
    if not buggy_code.strip():
        raise DailyGenerationError("Judge response is missing buggy_code (empty or truncated JSON)")

    buggy_line = data.get("buggy_line")
    if not isinstance(buggy_line, int) or isinstance(buggy_line, bool) or buggy_line <= 0:
        raise DailyGenerationError(f"Judge response has an invalid buggy_line: {buggy_line!r}")

    # A missing hint degrades gracefully (still playable); a missing
    # explanation in either language is not - the reveal would be blank.
    for key in ("explanation_vi", "explanation_en"):
        if not (data.get(key) or "").strip():
            raise DailyGenerationError(f"Judge response is missing {key}")

    challenge = DailyChallenge(
        challenge_date=challenge_date,
        prompt_title_vi=prompt["vi"],
        prompt_title_en=prompt["en"],
        buggy_code=buggy_code,
        buggy_line=buggy_line,
        bug_category=data.get("bug_category", "unknown"),
        hint_1_vi=data.get("hint_1_vi", ""),
        hint_1_en=data.get("hint_1_en", ""),
        hint_2_vi=data.get("hint_2_vi", ""),
        hint_2_en=data.get("hint_2_en", ""),
        explanation_vi=data["explanation_vi"],
        explanation_en=data["explanation_en"],
    )
    db.add(challenge)
    await db.commit()
    await db.refresh(challenge)
    return challenge
