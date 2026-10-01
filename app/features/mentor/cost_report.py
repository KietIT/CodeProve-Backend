"""Monthly LLM cost report (P3.6), from llm_calls and prompt_logs.

    python -m app.features.mentor.cost_report                  # this month (Vietnam time)
    python -m app.features.mentor.cost_report --month 2026-10

Prices come from .env (OPENAI_PRICE_INPUT_PER_M, OPENAI_PRICE_CACHED_PER_M,
OPENAI_PRICE_OUTPUT_PER_M, USD per million tokens). Copy them from OpenAI's
pricing page: without them the report shows tokens only. It prints counts,
never names or emails.
"""
import argparse
import asyncio
from collections import Counter
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import async_session_maker
from app.models import Attempt, LlmCall, PromptLog


class KindTotals(BaseModel):
    kind: str
    calls: int = 0
    prompt_tokens: int = 0
    cached_tokens: int = 0
    completion_tokens: int = 0
    usd: float = 0.0


class CostReport(BaseModel):
    month: str
    priced: bool  # False when no price is set: usd fields are 0
    kinds: list[KindTotals]  # most expensive (then most tokens) first
    total: KindTotals
    ciel_students: int  # students who sent Ciel at least one message
    ciel_mean_per_student: float
    ciel_max_per_student: int
    attempt_limit_hits: int  # attempts that used every Ciel message allowed
    daily_limit_hits: int  # (student, day) pairs that used every Ciel message allowed


def cost_usd(prompt: int, cached: int, completion: int, s: Settings) -> float:
    """Cached tokens are part of the prompt tokens and are billed at the cached price."""
    return ((prompt - cached) * s.openai_price_input_per_m + cached * s.openai_price_cached_per_m
            + completion * s.openai_price_output_per_m) / 1_000_000


def month_bounds(month: str, tz_name: str) -> tuple[datetime, datetime]:
    """[start, end) of a "YYYY-MM" month in the quota time zone, as UTC."""
    tz = ZoneInfo(tz_name)
    year, mon = (int(part) for part in month.split("-"))
    start = datetime(year, mon, 1, tzinfo=tz)
    end = datetime(year + mon // 12, mon % 12 + 1, 1, tzinfo=tz)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def _utc(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)  # SQLite gives naive UTC


async def build_report(db: AsyncSession, month: str, s: Settings | None = None) -> CostReport:
    s = s or get_settings()
    start, end = month_bounds(month, s.quota_timezone)
    rows = (await db.execute(
        select(LlmCall.kind, func.count(), func.sum(LlmCall.prompt_tokens), func.sum(LlmCall.cached_tokens),
               func.sum(LlmCall.completion_tokens))
        .where(LlmCall.created_at >= start, LlmCall.created_at < end).group_by(LlmCall.kind)
    )).all()
    kinds = [KindTotals(kind=kind, calls=n, prompt_tokens=p or 0, cached_tokens=c or 0, completion_tokens=o or 0,
                        usd=cost_usd(p or 0, c or 0, o or 0, s)) for kind, n, p, c, o in rows]
    kinds.sort(key=lambda k: (-k.usd, -(k.prompt_tokens + k.completion_tokens), k.kind))
    total = KindTotals(kind="total", calls=sum(k.calls for k in kinds),
                       prompt_tokens=sum(k.prompt_tokens for k in kinds),
                       cached_tokens=sum(k.cached_tokens for k in kinds),
                       completion_tokens=sum(k.completion_tokens for k in kinds),
                       usd=sum(k.usd for k in kinds))

    messages = (await db.execute(
        select(Attempt.user_id, PromptLog.attempt_id, PromptLog.created_at)
        .join(Attempt, Attempt.id == PromptLog.attempt_id)
        .where(PromptLog.created_at >= start, PromptLog.created_at < end)
    )).all()
    tz = ZoneInfo(s.quota_timezone)
    per_student = Counter(user_id for user_id, _, _ in messages)
    per_attempt = Counter(attempt_id for _, attempt_id, _ in messages)
    per_day = Counter((user_id, _utc(at).astimezone(tz).date()) for user_id, _, at in messages)
    return CostReport(
        month=month,
        priced=any((s.openai_price_input_per_m, s.openai_price_cached_per_m, s.openai_price_output_per_m)),
        kinds=kinds, total=total, ciel_students=len(per_student),
        ciel_mean_per_student=round(sum(per_student.values()) / len(per_student), 1) if per_student else 0.0,
        ciel_max_per_student=max(per_student.values(), default=0),
        attempt_limit_hits=sum(n >= s.ciel_per_attempt for n in per_attempt.values()),
        daily_limit_hits=sum(n >= s.ciel_per_day for n in per_day.values()),
    )


def render(r: CostReport) -> str:
    def line(k: KindTotals) -> str:
        cached = f"{k.cached_tokens / k.prompt_tokens:.0%}" if k.prompt_tokens else "-"
        cost = f"${k.usd:8.2f}" if r.priced else "       -"
        return (f"{k.kind:<18} {k.calls:>7} {k.prompt_tokens:>12} {cached:>7} {k.completion_tokens:>11} {cost}")

    out = [f"LLM usage {r.month}",
           f"{'kind':<18} {'calls':>7} {'input tok':>12} {'cached':>7} {'output tok':>11} {'cost':>8}"]
    out += [line(k) for k in r.kinds] + [line(r.total)]
    if not r.priced:
        out.append("No prices set: add OPENAI_PRICE_*_PER_M to .env (from OpenAI's pricing page) to see costs.")
    out += [f"Ciel: {r.ciel_students} student(s), {r.ciel_mean_per_student} message(s) each on average, "
            f"max {r.ciel_max_per_student}",
            f"Limits reached: {r.attempt_limit_hits} attempt(s), {r.daily_limit_hits} student-day(s)"]
    return "\n".join(out)


async def _main(month: str) -> int:
    async with async_session_maker() as db:
        print(render(await build_report(db, month)))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    this_month = datetime.now(ZoneInfo(get_settings().quota_timezone)).strftime("%Y-%m")
    parser.add_argument("--month", default=this_month, help="YYYY-MM (default: this month)")
    raise SystemExit(asyncio.run(_main(parser.parse_args().month)))
