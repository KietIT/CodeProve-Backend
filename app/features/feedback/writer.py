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
DEFAULT_TIMEOUT = 15.0
# Vietnamese costs roughly twice the tokens of English; a truncated JSON reply
# is unusable, so leave room for four full fields per finding.
TOKENS_BASE, TOKENS_PER_FINDING = 250, 450
_BLOCK = re.compile(r"```[\w+-]*\n?(.*?)```", re.DOTALL)
_EXERCISE = re.compile(r"\bCP-\d{3}\b")


def _strip_long_code(text: str) -> str:
    def replace(match: re.Match) -> str:
        lines = [line for line in match.group(1).split("\n") if line.strip()]
        return match.group(0) if len(lines) <= MAX_CODE_LINES else ""
    return _BLOCK.sub(replace, text).strip()


def _validated(item: dict, candidates: list[str]) -> tuple[tuple[dict[str, str], str | None] | None, str]:
    """((texts, suggested exercise), "") for a valid item, else (None, why it was rejected)."""
    texts = {}
    for field in FIELDS:
        value = item.get(field)
        if not isinstance(value, str):
            return None, f"missing_field:{field}"
        value = _strip_long_code(value)
        if not value:
            return None, f"empty_field:{field}"
        if len(value) > MAX_FIELD_CHARS:
            return None, f"too_long:{field}"
        texts[field] = value
    mentioned = set(_EXERCISE.findall(" ".join(texts.values())))
    suggested = str(item.get("next_exercise") or "").strip() or None
    if suggested and suggested not in candidates:
        return None, "next_not_a_candidate"
    if any(code not in candidates for code in mentioned):
        return None, "exercise_not_a_candidate"
    if suggested is None and mentioned:
        suggested = sorted(mentioned)[0]
    return (texts, suggested), ""


def _entry(finding: Finding, texts: dict[str, str], next_exercise: str | None, source: str,
           fallback_reason: str | None = None) -> dict:
    entry = {**finding.model_dump(), "text": texts, "next_exercise": next_exercise, "source": source}
    if fallback_reason:
        entry["fallback_reason"] = fallback_reason  # quality tracking: why the template was used
    return entry


def _prompt(locale: str, problem: str, findings: list[Finding], final_code: str, answers: list[dict],
            candidates: list[str]) -> str:
    code = "\n".join(final_code.split("\n")[:MAX_FINAL_CODE_LINES])
    suggested = candidates[0] if candidates else None
    payload = {
        "language": locale,
        "problem": problem,
        "findings": [{"code": f.code, "kind": f.kind, "axis": f.axis, "params": f.params, "evidence": f.evidence,
                      # The template is the house style the writer builds on (and the fallback).
                      "reference": render(f, locale, suggested)}
                     for f in findings],
        "explain_back": answers,
        "candidates": candidates,
    }
    return f"{json.dumps(payload, ensure_ascii=False, indent=1)}\nSTUDENT'S FINAL CODE:\n{code}"


async def write_feedback(client, *, locale: str, problem: str, findings: list[Finding], final_code: str,
                         answers: list[dict], candidates: list[str], timeout: float = DEFAULT_TIMEOUT) -> list[dict]:
    """One entry per finding (same order): the finding, its four texts, the suggested
    exercise, `source` ("llm" or "template") and, for a template, `fallback_reason`."""
    if not findings:
        return []
    fallback_next = candidates[0] if candidates else None
    written: dict[str, dict] = {}
    call_problem = None
    try:
        verdict = await asyncio.wait_for(
            client.judge(FEEDBACK_WRITER_SYSTEM, _prompt(locale, problem, findings, final_code, answers, candidates),
                         max_tokens=TOKENS_BASE + TOKENS_PER_FINDING * len(findings)),
            timeout)
        if not isinstance(verdict, dict) or not isinstance(verdict.get("items"), list):
            call_problem = "invalid_json"  # the client returns {} for unparsable (e.g. truncated) JSON
        else:
            for item in verdict["items"]:
                if isinstance(item, dict) and isinstance(item.get("code"), str):
                    written.setdefault(item["code"], item)
    except asyncio.TimeoutError:
        call_problem = "timeout"
    except Exception:  # never let the writer block a report: templates answer instead
        logger.warning("feedback writer failed; using templates", exc_info=True)
        call_problem = "call_failed"
    out = []
    for finding in findings:
        if finding.code in written:
            valid, reason = _validated(written[finding.code], candidates)
        else:
            valid, reason = None, call_problem or "no_item"
        if valid:
            out.append(_entry(finding, valid[0], valid[1], "llm"))
        else:
            out.append(_entry(finding, render(finding, locale, fallback_next), fallback_next, "template", reason))
    fallbacks = [e["fallback_reason"] for e in out if e["source"] == "template"]
    if fallbacks:
        logger.warning("feedback writer: %d/%d finding(s) on templates: %s", len(fallbacks), len(out), fallbacks)
    return out
