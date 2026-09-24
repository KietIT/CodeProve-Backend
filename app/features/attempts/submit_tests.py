"""Run an attempt's full test suite (visible + hidden) when it is submitted."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.features.attempts import service
from app.features.sandbox.runner import run_tests
from app.models import Attempt, TestCase

_SHOWN_CHARS = 300


def _clip(text: str | None) -> str | None:
    if text is None:
        return None
    return text if len(text) <= _SHOWN_CHARS else text[:_SHOWN_CHARS] + "…"


async def run_submit_suite(db: AsyncSession, attempt: Attempt) -> dict | None:
    """Run every test on the latest snapshot and log a SUBMIT_TESTS event.

    The frontend force-saves a snapshot right before submitting, so the latest
    snapshot is the submitted code. Returns the event payload, or None when the
    exercise has no tests.
    """
    tests = (await db.execute(
        select(TestCase).where(TestCase.exercise_id == attempt.exercise_id).order_by(TestCase.order_index)
    )).scalars().all()
    if not tests:
        return None
    code = await service.latest_code(db, attempt.id) or ""
    result = await run_tests(
        code,
        [{"input_data": t.input_data, "expected_output": t.expected_output,
          "description": t.description, "weight": t.weight} for t in tests],
        get_settings().sandbox_timeout,
    )
    # The sandbox returns one case per test, in the order given.
    pairs = list(zip(tests, result["cases"]))
    hidden = [(t, r) for t, r in pairs if t.is_hidden]
    failed = [(t, r) for t, r in pairs if not r["passed"]]
    payload = {
        "passRatio": result["coverage"],
        "passed": result["passed"],
        "total": result["total"],
        "visiblePassed": sum(r["passed"] for t, r in pairs if not t.is_hidden),
        "visibleTotal": len(pairs) - len(hidden),
        "hiddenPassed": sum(r["passed"] for _, r in hidden),
        "hiddenTotal": len(hidden),
        "failedCategories": sorted({t.category or "uncategorized" for t, _ in failed if t.is_hidden}),
        "failures": [
            {"description": t.description, "category": t.category, "hidden": t.is_hidden,
             "input": _clip(t.input_data), "expected": _clip(t.expected_output),
             "actual": _clip(r.get("actual")), "error": _clip(r.get("error"))}
            for t, r in failed
        ],
    }
    await service.add_event(db, attempt.id, "SUBMIT_TESTS", payload)
    return payload


def public_summary(payload: dict | None) -> dict | None:
    """What the student sees right after submitting: counts and categories, never inputs."""
    if payload is None:
        return None
    return {"passed": payload["passed"], "total": payload["total"],
            "hidden_passed": payload["hiddenPassed"], "hidden_total": payload["hiddenTotal"],
            "failed_categories": payload["failedCategories"]}
