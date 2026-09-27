"""Feedback text for the findings: reviewed templates plus one LLM-written line (P1.5).

The golden-set previews showed where the LLM helps: writing about THIS session
(round 1: specific "what happened", but vaguer advice than the templates;
round 2, given the templates: copied them verbatim 100/109 times). So the
advice fields (why_it_matters, how_to_improve, try_next) always come from the
team-reviewed templates, and the LLM writes only `what_happened`, which must
add a concrete detail of the session. One call per attempt, validated; any
item that fails keeps the template's line, and a failed or slow call falls
back entirely. Checks: the code is one of the findings; the line is non-empty,
at most MAX_FIELD_CHARS, not a copy of the template, suggests no exercise, and
loses code blocks longer than MAX_CODE_LINES lines (no solution leaks).

Only WRITTEN_CODES are written: the team review of round 3 flagged the LLM's
lines on strengths as restating the solution (13/39 leak flags) and a
verification line citing code the session did not show; counts are misread.
The writer never sees the final code, so it cannot quote or describe it.
"""
import asyncio
import json
import logging
import re

from app.features.feedback.diagnosis import Finding
from app.features.feedback.templates import render
from app.features.mentor.prompts import FEEDBACK_WRITER_SYSTEM

logger = logging.getLogger(__name__)

MAX_FIELD_CHARS = 400
MAX_CODE_LINES = 2
DEFAULT_TIMEOUT = 15.0
TOKENS_BASE, TOKENS_PER_FINDING = 200, 200
# Risks whose evidence is the student's own words, and where saying which words helps:
# explain-back answers, a vague hypothesis, a vague prompt. Everything else keeps its
# reviewed template line (strengths would restate the approach; counts and AI-code
# findings are stated exactly by the template).
WRITTEN_CODES = {"explain_missing", "explain_shallow", "hypothesis_vague", "prompts_vague"}
_BLOCK = re.compile(r"```[\w+-]*\n?(.*?)```", re.DOTALL)
_EXERCISE = re.compile(r"\bCP-\d{3}\b")


def _strip_long_code(text: str) -> str:
    def replace(match: re.Match) -> str:
        lines = [line for line in match.group(1).split("\n") if line.strip()]
        return match.group(0) if len(lines) <= MAX_CODE_LINES else ""
    return _BLOCK.sub(replace, text).strip()


def _normalized(text: str) -> str:
    return " ".join(text.lower().split()).rstrip(".")


def _validated(item: dict, template_line: str) -> tuple[str | None, str]:
    """(line, "") for a usable `what_happened`, else (None, why it was rejected)."""
    value = item.get("what_happened")
    if not isinstance(value, str):
        return None, "missing_field:what_happened"
    value = _strip_long_code(value)
    if not value:
        return None, "empty_field:what_happened"
    if len(value) > MAX_FIELD_CHARS:
        return None, "too_long:what_happened"
    if _EXERCISE.search(value):
        return None, "exercise_mentioned"
    if _normalized(value) == _normalized(template_line):
        return None, "copied_template"
    return value, ""


def _prompt(locale: str, problem: str, findings: list[Finding], answers: list[dict]) -> str:
    payload = {
        "language": locale,
        "problem": problem,
        "findings": [{"code": f.code, "kind": f.kind, "axis": f.axis, "params": f.params, "evidence": f.evidence,
                      "generic_line": render(f, locale, None)["what_happened"]}
                     for f in findings],
        "explain_back": answers,
    }
    return json.dumps(payload, ensure_ascii=False, indent=1)


async def _ask(client, locale: str, problem: str, findings: list[Finding], answers: list[dict],
               timeout: float) -> tuple[dict[str, dict], str | None]:
    """The writer's items by finding code, and what went wrong with the call (None if nothing)."""
    try:
        verdict = await asyncio.wait_for(
            client.judge(FEEDBACK_WRITER_SYSTEM, _prompt(locale, problem, findings, answers),
                         max_tokens=TOKENS_BASE + TOKENS_PER_FINDING * len(findings)),
            timeout)
    except asyncio.TimeoutError:
        return {}, "timeout"
    except Exception:  # never let the writer block a report: templates answer instead
        logger.warning("feedback writer failed; using templates", exc_info=True)
        return {}, "call_failed"
    if not isinstance(verdict, dict) or not isinstance(verdict.get("items"), list):
        return {}, "invalid_json"  # the client returns {} for unparsable (e.g. truncated) JSON
    written: dict[str, dict] = {}
    for item in verdict["items"]:
        if isinstance(item, dict) and isinstance(item.get("code"), str):
            written.setdefault(item["code"], item)
    return written, None


async def write_feedback(client, *, locale: str, problem: str, findings: list[Finding], answers: list[dict],
                         candidates: list[str], timeout: float = DEFAULT_TIMEOUT) -> list[dict]:
    """One entry per finding (same order): the finding, its four texts, the suggested
    exercise, `source` ("llm" when `what_happened` was written for this session,
    else "template") and, for a template line, `fallback_reason`."""
    if not findings:
        return []
    next_exercise = candidates[0] if candidates else None
    to_write = [f for f in findings if f.code in WRITTEN_CODES]
    written, call_problem = (await _ask(client, locale, problem, to_write, answers, timeout)
                             if to_write else ({}, None))
    out = []
    for finding in findings:
        texts = render(finding, locale, next_exercise)
        entry = {**finding.model_dump(), "text": texts, "next_exercise": next_exercise, "source": "template"}
        if finding.code not in WRITTEN_CODES:
            out.append(entry)  # template by design, not a failure: no fallback_reason
            continue
        if finding.code in written:
            line, reason = _validated(written[finding.code], texts["what_happened"])
        else:
            line, reason = None, call_problem or "no_item"
        if line:
            texts["what_happened"] = line
            entry["source"] = "llm"
        else:
            entry["fallback_reason"] = reason  # quality tracking: why the template line was kept
        out.append(entry)
    kept = [e["fallback_reason"] for e in out if "fallback_reason" in e]
    if kept:
        logger.warning("feedback writer: %d/%d finding(s) kept the template line: %s", len(kept), len(out), kept)
    return out
