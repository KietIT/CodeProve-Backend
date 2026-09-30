"""Anchored LLM judges for rubric v2 (P1.4).

Each judge rates student text on the rating guide's 0-3 levels and quotes the
words that justify it. A verdict without a valid level stays None (the
indicator is then N/A); a level is never invented. The hypothesis and
explain-back judges share their existing call with v1 (same request, extra
fields), so v2 adds exactly one call per attempt: all prompts to Ciel at once.
Verdicts are stored as events by the callers so a rescore never re-asks the LLM.
"""
import logging
import math

from app.features.mentor.prompts import (
    EXPLAIN_SCORE_SYSTEM, HYPOTHESIS_JUDGE_SYSTEM, LOCATE_JUDGE_SYSTEM, PROMPT_JUDGE_SYSTEM,
)

logger = logging.getLogger(__name__)

MAX_EVIDENCE = 160
MAX_PROMPT_CHARS = 1500


def level_of(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number != int(number) or not 0 <= number <= 3:
        return None
    return int(number)


def _evidence(value: object) -> str:
    return str(value).strip()[:MAX_EVIDENCE] if value else ""


def is_non_answer(answer: str) -> bool:
    """A trivially short reply cannot show understanding (the pre-P1.4 guard)."""
    text = (answer or "").strip()
    return len(text) < 15 or len(text.split()) < 4


async def judge_explain(client, question: str, answer: str, context: str = "") -> dict:
    """{"score": 0-20 (v1), "level": 0-3 | None, "evidence": str} for one explain-back answer.
    `context` (P2.5): the student's final code and the submit-suite result, so an answer that
    calls code correct while the tests show it wrong is not rated strong."""
    if is_non_answer(answer):
        return {"score": 0.0, "level": 0, "evidence": ""}
    user = f"Question: {question}\nAnswer: {answer}"
    verdict = await client.judge(EXPLAIN_SCORE_SYSTEM, f"{context}\n\n{user}" if context else user)
    try:
        score = float(verdict.get("score", 0))
    except (TypeError, ValueError):
        score = 0.0
    return {"score": max(0.0, min(20.0, score)), "level": level_of(verdict.get("level")),
            "evidence": _evidence(verdict.get("evidence"))}


async def judge_hypothesis(client, problem: str, text: str) -> dict:
    """The existing correct/note verdict plus the rubric level and its evidence."""
    verdict = await client.judge(HYPOTHESIS_JUDGE_SYSTEM, f"Problem: {problem}\nStudent hypothesis: {text}")
    return {"correct": bool(verdict.get("correct", False)), "note": verdict.get("note", ""),
            "level": level_of(verdict.get("level")), "evidence": _evidence(verdict.get("evidence"))}


async def judge_locate(client, served_starter: str, explanation: str, lines: list[int], reason: str) -> dict:
    """P2.2: how well the one-sentence reason of the locate step explains the real bug.
    Trivial reasons are level 0 without a call; a failed call leaves it unrated (None)."""
    if is_non_answer(reason):
        return {"level": 0, "evidence": ""}
    numbered = "\n".join(f"{i} | {line}" for i, line in enumerate(served_starter.split("\n"), start=1))
    user = (f"Code:\n{numbered}\n\nReal bug: {explanation}\n\n"
            f"Selected lines: {', '.join(map(str, lines)) or '(none)'}\nStudent's reason: {reason}")
    try:
        verdict = await client.judge(LOCATE_JUDGE_SYSTEM, user)
    except Exception:  # never block scoring: the indicator becomes N/A instead
        logger.warning("locate judge failed; reason left unrated", exc_info=True)
        return {"level": None, "evidence": ""}
    return {"level": level_of(verdict.get("level")), "evidence": _evidence(verdict.get("evidence"))}


def _unrated() -> dict:
    return {"level": None, "evidence": "", "asks_for_solution": False, "questions_ai_code": False}


async def judge_prompts(client, problem: str, prompts: list[str]) -> list[dict]:
    """One verdict per prompt, in order, from a single call. A failed call or a
    missing entry leaves that prompt unrated (level None)."""
    if not prompts:
        return []
    numbered = "\n".join(f"{i}. {text[:MAX_PROMPT_CHARS]}" for i, text in enumerate(prompts, start=1))
    try:
        verdict = await client.judge(PROMPT_JUDGE_SYSTEM, f"Problem: {problem}\nMessages:\n{numbered}",
                                     max_tokens=120 + 90 * len(prompts))
    except Exception:  # the new judge must never block scoring
        logger.warning("prompt judge failed; prompts left unrated", exc_info=True)
        return [_unrated() for _ in prompts]
    by_number: dict[int, dict] = {}
    for item in verdict.get("prompts") or []:
        if not isinstance(item, dict):
            continue
        try:
            by_number.setdefault(int(item.get("i")), item)
        except (TypeError, ValueError):
            continue
    out = []
    for i in range(1, len(prompts) + 1):
        item = by_number.get(i)
        if item is None:
            out.append(_unrated())
            continue
        out.append({"level": level_of(item.get("level")), "evidence": _evidence(item.get("evidence")),
                    "asks_for_solution": bool(item.get("asks_for_solution")),
                    "questions_ai_code": bool(item.get("questions_ai_code"))})
    return out
