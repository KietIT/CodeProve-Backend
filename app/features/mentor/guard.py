"""Code-enforced no-solution rule for Ciel (P2.1).

The system prompt tells Ciel never to write the solution, but the golden set
showed it can (P1.3, sim-02: "I can't write the full code" followed by a
nearly complete `two_sum` that passed 8/8). So before a reply is shown, its
code blocks run against the exercise's visible tests in the sandbox; code that
passes all of them is a solution, and the reply is withheld (the service asks
Ciel once more with a stricter rule, then falls back to FALLBACK).

Fails open: with no visible tests, or when the sandbox cannot run the code,
the reply is shown (logged), because the sandbox being down also stops runs
and submits, and a silent block would hide Ciel entirely.
"""
import logging
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.features.sandbox.runner import run_tests
from app.models import TestCase

logger = logging.getLogger(__name__)

_CODE_BLOCK = re.compile(r"```[a-zA-Z0-9_+-]*\n(.*?)```", re.DOTALL)

RETRY_INSTRUCTION = (
    "IMPORTANT: your previous draft contained code that already solves this exercise, so it was not shown. "
    "Answer again WITHOUT any code that implements the solution: explain the idea, point to the relevant "
    "concept or the part of the student's code to look at, and ask a guiding question. A one-line snippet "
    "that does not solve the task is allowed."
)
# Shown when the retry still contains a solution. Both languages: the student's language is not known here.
FALLBACK = (
    "Mình không thể đưa code giải sẵn cho bài này. Hãy cho mình biết bạn đang vướng ở bước nào hoặc test nào "
    "đang fail, mình sẽ gợi ý hướng đi.\n\n"
    "I can't give you code that solves this exercise. Tell me which step you are stuck on or which test "
    "fails, and I'll point you in the right direction."
)


def code_blocks(text: str) -> list[str]:
    return _CODE_BLOCK.findall(text)


async def solves_exercise(db: AsyncSession, exercise_id: int, text: str) -> bool:
    """True when the reply's code blocks, together, pass every visible test."""
    blocks = code_blocks(text)
    if not blocks:
        return False
    cases = (await db.execute(
        select(TestCase).where(TestCase.exercise_id == exercise_id, TestCase.is_hidden.is_(False))
        .order_by(TestCase.order_index)
    )).scalars().all()
    if not cases:
        return False
    case_dicts = [{"input_data": c.input_data, "expected_output": c.expected_output,
                   "description": c.description, "weight": c.weight} for c in cases]
    try:
        result = await run_tests("\n\n".join(blocks), case_dicts, get_settings().sandbox_timeout)
    except Exception:  # fail open, see the module docstring
        logger.warning("no-solution guard could not run a Ciel reply; showing it", exc_info=True)
        return False
    return result["total"] > 0 and result["passed"] == result["total"]
