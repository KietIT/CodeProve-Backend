"""Feedback text for the findings: one LLM call, validated, with template fallback (P1.5).

The writer may only explain the findings it is given. Each written item is
checked before use; an item that fails any check is replaced by its template,
and a failed or slow call falls back to templates for everything. Checks:
the code is one of the findings; every field is non-empty and at most
MAX_FIELD_CHARS; code blocks longer than MAX_CODE_LINES lines are removed (the
report is shown right after submit, so it must not hand over a solution);
any exercise it suggests is one of the candidates.
"""
import asyncio
import json
import logging
import re

from app.features.feedback.diagnosis import Finding
from app.features.feedback.templates import FIELDS, render
from app.features.mentor.prompts import FEEDBACK_WRITER_SYSTEM

logger = logging.getLogger(__name__)

MAX_FIELD_CHARS = 400
MAX_CODE_LINES = 2
MAX_FINAL_CODE_LINES = 60
DEFAULT_TIMEOUT = 12.0
_BLOCK = re.compile(r"```[\w+-]*\n?(.*?)```", re.DOTALL)
_EXERCISE = re.compile(r"\bCP-\d{3}\b")


def _strip_long_code(text: str) -> str:
    def replace(match: re.Match) -> str:
        lines = [line for line in match.group(1).split("\n") if line.strip()]
        return match.group(0) if len(lines) <= MAX_CODE_LINES else ""
    return _BLOCK.sub(replace, text).strip()


def _validated(item: dict, candidates: list[str]) -> tuple[dict[str, str], str | None] | None:
    """(texts, suggested exercise) for a valid item, else None."""
    texts = {}
    for field in FIELDS:
        value = item.get(field)
        if not isinstance(value, str):
            return None
        value = _strip_long_code(value)
        if not value or len(value) > MAX_FIELD_CHARS:
            return None
        texts[field] = value
    mentioned = set(_EXERCISE.findall(" ".join(texts.values())))
    suggested = str(item.get("next_exercise") or "").strip() or None
    if suggested and suggested not in candidates:
        return None
    if any(code not in candidates for code in mentioned):
        return None
    if suggested is None and mentioned:
        suggested = sorted(mentioned)[0]
    return texts, suggested


def _entry(finding: Finding, texts: dict[str, str], next_exercise: str | None, source: str) -> dict:
    return {**finding.model_dump(), "text": texts, "next_exercise": next_exercise, "source": source}


def _prompt(locale: str, problem: str, findings: list[Finding], final_code: str, answers: list[dict],
            candidates: list[str]) -> str:
    code = "\n".join(final_code.split("\n")[:MAX_FINAL_CODE_LINES])
    payload = {
        "language": locale,
        "problem": problem,
        "findings": [{"code": f.code, "kind": f.kind, "axis": f.axis, "params": f.params, "evidence": f.evidence}
                     for f in findings],
        "explain_back": answers,
        "candidates": candidates,
    }
    return f"{json.dumps(payload, ensure_ascii=False, indent=1)}\nSTUDENT'S FINAL CODE:\n{code}"


async def write_feedback(client, *, locale: str, problem: str, findings: list[Finding], final_code: str,
                         answers: list[dict], candidates: list[str], timeout: float = DEFAULT_TIMEOUT) -> list[dict]:
    """One entry per finding (same order): the finding, its four texts, the suggested
    exercise and `source` ("llm" or "template")."""
    if not findings:
        return []
    fallback_next = candidates[0] if candidates else None
    written: dict[str, dict] = {}
    try:
        verdict = await asyncio.wait_for(
            client.judge(FEEDBACK_WRITER_SYSTEM, _prompt(locale, problem, findings, final_code, answers, candidates),
                         max_tokens=150 + 260 * len(findings)),
            timeout)
        for item in verdict.get("items") or []:
            if isinstance(item, dict) and isinstance(item.get("code"), str):
                written.setdefault(item["code"], item)
    except Exception:  # never let the writer block a report: templates answer instead
        logger.warning("feedback writer failed; using templates", exc_info=True)
    out = []
    for finding in findings:
        valid = _validated(written[finding.code], candidates) if finding.code in written else None
        if valid:
            out.append(_entry(finding, valid[0], valid[1], "llm"))
        else:
            out.append(_entry(finding, render(finding, locale, fallback_next), fallback_next, "template"))
    return out
