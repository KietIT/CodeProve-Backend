"""P3.6: monthly LLM cost report."""
from datetime import datetime, timezone

import pytest

from app.core.config import Settings
from app.features.mentor.cost_report import build_report, cost_usd, month_bounds, render
from app.models import Attempt, Exercise, LlmCall, PromptLog, User

# Test prices only (not OpenAI's): round numbers make the maths easy to check.
PRICED = Settings(openai_price_input_per_m=1.0, openai_price_cached_per_m=0.5, openai_price_output_per_m=4.0,
                  ciel_per_attempt=3, ciel_per_day=4)
UNPRICED = Settings(ciel_per_attempt=3, ciel_per_day=4)


def utc(*args) -> datetime:
    return datetime(*args, tzinfo=timezone.utc)


def test_cached_tokens_are_billed_at_the_cached_price():
    assert cost_usd(1_000_000, 400_000, 100_000, PRICED) == pytest.approx(0.6 + 0.2 + 0.4)


def test_the_month_follows_vietnam_time():
    start, end = month_bounds("2026-10", "Asia/Ho_Chi_Minh")
    assert (start, end) == (utc(2026, 9, 30, 17), utc(2026, 10, 31, 17))
    assert month_bounds("2026-12", "Asia/Ho_Chi_Minh")[1] == utc(2026, 12, 31, 17)  # rolls into next year


async def _seed(db):
    an = User(full_name="An", email="an@student.vn", password_hash="x")
    binh = User(full_name="Binh", email="binh@student.vn", password_hash="x")
    ex = Exercise(code="CP-001", title="t", difficulty="Easy", category="c", level="junior", language="python",
                  summary="s", starter_code="", hint="h", domain_keywords=[])
    db.add_all([an, binh, ex]); await db.flush()
    a1, a2, b1 = (Attempt(user_id=u.id, exercise_id=ex.id) for u in (an, an, binh))
    db.add_all([a1, a2, b1]); await db.flush()
    in_month, before = utc(2026, 10, 5, 3), utc(2026, 9, 30, 16, 59)  # 23:59 on Sep 30 in Vietnam
    db.add_all([
        LlmCall(kind="ciel", model="m", prompt_tokens=2_000_000, cached_tokens=1_000_000, completion_tokens=100_000,
                user_id=an.id, attempt_id=a1.id, created_at=in_month),
        LlmCall(kind="ciel", model="m", prompt_tokens=1_000_000, cached_tokens=0, completion_tokens=50_000,
                user_id=binh.id, attempt_id=b1.id, created_at=in_month),
        LlmCall(kind="explain", model="m", prompt_tokens=500_000, cached_tokens=0, completion_tokens=10_000,
                created_at=in_month),
        LlmCall(kind="ciel", model="m", prompt_tokens=9_000_000, cached_tokens=0, completion_tokens=0,
                created_at=before),  # September in Vietnam time: not counted
    ])
    # An: 3 messages in attempt a1 (attempt limit) + 1 in a2 = 4 on Oct 5 (daily limit). Binh: 1.
    db.add_all([PromptLog(attempt_id=a1.id, prompt="q", response="r", created_at=in_month) for _ in range(3)])
    db.add_all([PromptLog(attempt_id=a2.id, prompt="q", response="r", created_at=in_month),
                PromptLog(attempt_id=b1.id, prompt="q", response="r", created_at=in_month),
                PromptLog(attempt_id=b1.id, prompt="q", response="r", created_at=before)])
    await db.commit()


async def test_the_report_totals_tokens_cost_and_limits(db_session):
    await _seed(db_session)
    r = await build_report(db_session, "2026-10", PRICED)
    assert [k.kind for k in r.kinds] == ["ciel", "explain"]
    ciel = r.kinds[0]
    assert (ciel.calls, ciel.prompt_tokens, ciel.cached_tokens, ciel.completion_tokens) == \
        (2, 3_000_000, 1_000_000, 150_000)
    assert ciel.usd == pytest.approx(2.0 + 0.5 + 0.6)
    assert r.total.calls == 3 and r.total.usd == pytest.approx(3.1 + 0.5 + 0.04)
    assert (r.ciel_students, r.ciel_mean_per_student, r.ciel_max_per_student) == (2, 2.5, 4)
    assert (r.attempt_limit_hits, r.daily_limit_hits) == (1, 1)
    text = render(r)
    assert "ciel" in text and "$    3.10" in text and "33%" in text and "@" not in text


async def test_without_prices_the_report_shows_tokens_only(db_session):
    await _seed(db_session)
    r = await build_report(db_session, "2026-10", UNPRICED)
    assert not r.priced and r.total.usd == 0
    assert "No prices set" in render(r)


async def test_an_empty_month(db_session):
    r = await build_report(db_session, "2026-11", PRICED)
    assert r.kinds == [] and r.total.calls == 0 and r.ciel_students == 0 and r.ciel_max_per_student == 0
    assert "total" in render(r)
