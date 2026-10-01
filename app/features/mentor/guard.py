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
from app.features.exercises.starters import student_starter
from app.features.mentor import overlap
from app.features.sandbox.runner import run_tests
from app.models import Exercise, PromptLog, TestCase

logger = logging.getLogger(__name__)

_CODE_BLOCK = re.compile(r"```[a-zA-Z0-9_+-]*\n(.*?)```", re.DOTALL)

RETRY_INSTRUCTION = (
    "IMPORTANT: your previous draft contained code that already solves this exercise, so it was not shown. "
    "Answer again WITHOUT any code that implements the solution: explain the idea, point to the relevant "
    "concept or the part of the student's code to look at, and ask a guiding question. A one-line snippet "
    "that does not solve the task is allowed."
)
OVERLAP_RETRY_INSTRUCTION = (
    "IMPORTANT: your previous draft, together with the code you already showed earlier in this "
    "conversation, gave away a large part of this exercise's solution, so it was not shown. Answer again "
    "with NO code for any step of this exercise (not renamed, not as an example in another context): "
    "explain the idea in words and ask a guiding question."
)
# Shown when the retry still contains a solution. Both languages: the student's language is not known here.
FALLBACK = (
    "Mình không thể đưa code giải sẵn cho bài này. Hãy cho mình biết bạn đang vướng ở bước nào hoặc test nào "
    "đang fail, mình sẽ gợi ý hướng đi.\n\n"
    "I can't give you code that solves this exercise. Tell me which step you are stuck on or which test "
    "fails, and I'll point you in the right direction."
)


# Debug exercises (P2.2): until the student has located the bug, Ciel only helps them find it.
LOCATE_INSTRUCTION = (
    "This is a debug exercise and the student has NOT found the bug yet. Do NOT say which line, statement "
    "or expression is wrong, do not quote or rewrite the buggy code, do not give line numbers, and do not "
    "describe the fix. Only help them find it themselves: suggest tracing the code with a small input (the "
    "Visualizer shows every step), comparing the actual result with the expected one, and ask guiding "
    "questions about what each part of the code should do. This rule overrides any HINT STYLE above."
)
LOCATE_RETRY_INSTRUCTION = (
    "IMPORTANT: your previous draft pointed at the buggy line, so it was not shown. Answer again with "
    "guiding hints only: no line numbers, no quoted code from the exercise, no fix."
)
BUG_FALLBACK = (
    "Mình chưa thể chỉ ra dòng lỗi khi bạn chưa tìm ra nó. Hãy thử một input nhỏ, tự tính kết quả mong đợi, "
    "rồi chạy code trong Visualizer để xem từ bước nào kết quả bắt đầu khác.\n\n"
    "I can't point at the buggy line before you have found it. Try a small input, work out the expected "
    "result, then run the code in the Visualizer to see at which step the result starts to differ."
)
QUOTE_MIN_CHARS = 8  # shorter lines (e.g. "else:") are too common to count as quoting the bug
_LINE_REF = re.compile(r"\b(?:lines?|dòng)\s+(\d+)(?:\s*(?:-|–|to|đến|and|và|,)\s*(\d+))?", re.IGNORECASE)


def _squash(text: str) -> str:
    return " ".join(text.split())


def reveals_bug(text: str, served_starter: str, regions: list[list[int]]) -> bool:
    """True when a reply quotes a line of the bug region or refers to one by number
    (including a range that covers it)."""
    bug_lines = {line for region in regions for line in region}
    starter = served_starter.replace("\r\n", "\n").split("\n")
    reply = _squash(text)
    for n in bug_lines:
        quoted = _squash(starter[n - 1]) if 1 <= n <= len(starter) else ""
        if len(quoted) >= QUOTE_MIN_CHARS and quoted in reply:
            return True
    for match in _LINE_REF.finditer(text):
        lo = int(match.group(1))
        hi = int(match.group(2)) if match.group(2) else lo
        if any(min(lo, hi) <= n <= max(lo, hi) for n in bug_lines):
            return True
    return False


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


async def leaks_solution(db: AsyncSession, ex: Exercise, attempt_id: int, text: str) -> bool:
    """True when the code in this reply, added to the code Ciel already showed in the attempt, covers at
    least overlap.OVERLAP_THRESHOLD of the reference solution's core (fix 2026-10-01: pieces over several
    replies). Fails open without a reference solution."""
    if not ex.reference_solution:
        return False
    earlier = (await db.execute(select(PromptLog.response).where(PromptLog.attempt_id == attempt_id))).scalars().all()
    code = [block for reply in [*earlier, text] for block in overlap.snippets(reply or "")]
    if not overlap.snippets(text or ""):
        return False  # nothing new in this reply: it cannot be the one that gives the solution away
    starter = student_starter(ex.starter_code or "", ex.kind or "implement")
    return overlap.coverage(ex.reference_solution, starter, code) >= overlap.OVERLAP_THRESHOLD
