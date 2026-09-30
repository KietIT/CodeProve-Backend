"""Findings from rubric v2 evidence (P1.5): what the feedback is allowed to talk about.

`diagnose` is deterministic and only reads what engine v2 already established
(levels, reason codes, evidence quotes) plus a few facts from the session
(failed test categories, prompt flags). Feedback text is written later from
these findings, so it can never criticise something the session did not show.
The finding codes are the contract with the frontend (docs/api/feedback.md).
"""
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.features.scoring import rubric
from app.features.scoring.engine import WEIGHTS
from app.features.scoring.evidence import Evidence

MAX_RISKS = 3
MAX_STRENGTHS = 2
MAX_FAILED_TESTS = 3
# The catalog of the P1.5 plan; every code has templates in both locales.
FINDING_CODES = (
    "explain_missing", "explain_shallow", "explain_strong",
    "no_hypothesis", "hypothesis_vague", "hypothesis_after_code", "hypothesis_strong",
    "asked_for_solution", "prompts_vague", "prompts_strong",
    "pasted_ai_failing", "pasted_ai_unchecked", "adapted_ai_code", "questioned_ai_code",
    "never_ran_tests", "submitted_failing", "hidden_edge_failed", "all_tests_passed",
    "bug_not_fixed", "partial_fix", "trial_and_error", "quick_fix",
    "integrity_flags",
    # P2.2, debug exercises with the locate step
    "bug_located", "bug_not_located", "bug_explained_well", "bug_explanation_weak",
)
_SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}
# Integrity problems are said first: they undermine every other axis.
_AXIS_RANK = {**WEIGHTS, "overall": 1.0}


class Finding(BaseModel):
    code: str
    axis: str
    kind: Literal["strength", "risk"]
    severity: Literal["high", "medium", "low"] | None = None
    params: dict = Field(default_factory=dict)
    evidence: str = ""

    @field_validator("code")
    @classmethod
    def _known(cls, code: str) -> str:
        if code not in FINDING_CODES:
            raise ValueError(f"unknown finding code {code!r}")
        return code


def _risk(code: str, axis: str, severity: str, evidence: str = "", **params) -> Finding:
    return Finding(code=code, axis=axis, kind="risk", severity=severity, params=params, evidence=evidence)


def _strength(code: str, axis: str, evidence: str = "") -> Finding:
    return Finding(code=code, axis=axis, kind="strength", evidence=evidence)


def _understanding(level, quote, reason) -> list[Finding]:
    if level == 0:
        return [_risk("explain_missing", "understanding", "high", quote)]
    if level in (1, 2):
        return [_risk("explain_shallow", "understanding", "medium", quote)]
    return [_strength("explain_strong", "understanding", quote)] if level == 3 else []


def _hypothesis(level, quote, reason) -> list[Finding]:
    if reason == "no_hypothesis":
        return [_risk("no_hypothesis", "hypothesis", "medium")]
    if reason == "after_code":
        return [_risk("hypothesis_after_code", "hypothesis", "low", quote)]
    if level == 1:
        return [_risk("hypothesis_vague", "hypothesis", "low", quote)]
    return [_strength("hypothesis_strong", "hypothesis", quote)] if level == 3 else []


def _prompting(level, quote, reason, ev: Evidence) -> list[Finding]:
    if level is None:
        return []
    out = []
    asked = sum(rubric.prompt_flags(ev, "asks_for_solution"))
    if asked:
        out.append(_risk("asked_for_solution", "prompting", "high", count=asked))
    elif level <= 1:
        out.append(_risk("prompts_vague", "prompting", "medium", quote))
    if level == 3:
        out.append(_strength("prompts_strong", "prompting", quote))
    return out


def _verification(level, quote, reason) -> list[Finding]:
    if reason == "pasted_unchanged":
        code, severity = ("pasted_ai_failing", "high") if level == 0 else ("pasted_ai_unchecked", "medium")
        return [_risk(code, "verification", severity, quote)]
    if reason == "pasted_changed" and level == 3:
        return [_strength("adapted_ai_code", "verification", quote)]
    if reason == "questioned":
        return [_strength("questioned_ai_code", "verification", quote)]
    return []


def _failed_hidden(suite: dict) -> dict:
    """Categories and names of the hidden tests that failed at submit. The names ("limit of
    one") make the advice fit the exercise; the student sees these failures on the Feedback
    page anyway (P1.2 policy), and inputs/expected outputs are never included here."""
    names = []
    for failure in suite.get("failures") or []:
        name = (failure.get("description") or "").strip()
        if failure.get("hidden") and name:
            name = name.removeprefix("test_").replace("_", " ") if " " not in name else name
            if name not in names:
                names.append(name)
    return {"failed_categories": list(suite.get("failedCategories") or []),
            "failed_tests": names[:MAX_FAILED_TESTS]}


def _testing(level, quote, reason, ev: Evidence, parts: dict | None = None) -> list[Finding]:
    suite = ev.submit_suite or {}
    if parts:  # P2.3: the axis also covers the student's tests; these findings are about correctness
        level = parts["correctness"]
    if reason == "never_ran":
        return [_risk("never_ran_tests", "testing", "high")]
    if level in (0, 1):
        return [_risk("submitted_failing", "testing", "high", quote,
                      passed=suite.get("passed", 0), total=suite.get("total", 0))]
    if level == 2 and reason == "hidden_fail":
        return [_risk("hidden_edge_failed", "testing", "medium", quote, **_failed_hidden(suite))]
    return [_strength("all_tests_passed", "testing", quote)] if level == 3 else []


def _locate(parts: dict) -> list[Finding]:
    """Findings of the P2.2 locate step (the bug itself is named by the report's reveal, not here)."""
    out = []
    if parts["skipped"] or parts["located"] == 0:
        out.append(_risk("bug_not_located", "debugging", "medium", hints_used=parts["hints_used"]))
    elif parts["located"] == 3:
        out.append(_strength("bug_located", "debugging"))
    explained = parts["explained"]
    if not parts["skipped"] and explained is not None:
        if explained <= 1:
            out.append(_risk("bug_explanation_weak", "debugging", "low"))
        elif explained == 3:
            out.append(_strength("bug_explained_well", "debugging"))
    return out


def _debugging(level, quote, reason, ev: Evidence, parts: dict | None = None) -> list[Finding]:
    suite = ev.submit_suite or {}
    if parts:  # debug exercise with the locate step: the fix part has its own levels
        fix = []
        if parts["fixed"] <= 1:
            fix = [_risk("bug_not_fixed", "debugging", "high", quote,
                         passed=suite.get("passed", 0), total=suite.get("total", 0))]
        elif parts["fixed"] == 2:
            fix = [_risk("partial_fix", "debugging", "medium", quote, **_failed_hidden(suite))]
        elif parts["efficiency"] == 1:
            fix = [_risk("trial_and_error", "debugging", "medium", quote, failing_runs=rubric.failing_runs(ev))]
        elif parts["efficiency"] == 3:
            fix = [_strength("quick_fix", "debugging", quote)]
        return _locate(parts) + fix
    if reason == "not_fixed":
        return [_risk("bug_not_fixed", "debugging", "high", quote,
                      passed=suite.get("passed", 0), total=suite.get("total", 0))]
    if reason == "partially_fixed":
        return [_risk("partial_fix", "debugging", "medium", quote, **_failed_hidden(suite))]
    if reason == "fixed" and level == 1:
        return [_risk("trial_and_error", "debugging", "medium", quote, failing_runs=rubric.failing_runs(ev))]
    return [_strength("quick_fix", "debugging", quote)] if reason == "fixed" and level == 3 else []


def diagnose(result: dict, ev: Evidence) -> list[Finding]:
    """Ranked findings for an engine v2 result: at most MAX_RISKS risks (worst
    first) and MAX_STRENGTHS strengths (highest-weight axis first)."""
    levels, evidence = result["levels"], result["evidence"]

    def args(axis: str) -> tuple:
        return levels[axis], evidence[axis]["evidence"], evidence[axis]["reason"]

    found = [
        *_understanding(*args("understanding")),
        *_hypothesis(*args("hypothesis")),
        *_prompting(*args("prompting"), ev),
        *_verification(*args("verification")),
        *_testing(*args("testing"), ev, evidence["testing"].get("parts")),
        *_debugging(*args("debugging"), ev, evidence["debugging"].get("parts")),
    ]
    # A failing submit is both an unfixed bug and a submit decision, and a hidden edge
    # failure after a fix is both a testing gap and a partial fix: say each once (team
    # review of round 3). Debug exercises talk about the fix, others about the submit.
    codes = {x.code for x in found}
    if "partial_fix" in codes:
        found = [x for x in found if x.code != "hidden_edge_failed"]
    if {"bug_not_fixed", "submitted_failing"} <= codes:
        drop = "submitted_failing" if ev.exercise_kind == "debug" else "bug_not_fixed"
        found = [x for x in found if x.code != drop]
    if result["integrity_multiplier"] < 1.0:
        f = result["features"]
        found.append(_risk("integrity_flags", "overall", "high", paste=f.paste_flags, focus_lost=f.focus_lost))

    risks = sorted((x for x in found if x.kind == "risk"),
                   key=lambda x: (_SEVERITY_RANK[x.severity], -_AXIS_RANK[x.axis]))
    strengths = sorted((x for x in found if x.kind == "strength"), key=lambda x: -_AXIS_RANK[x.axis])
    return risks[:MAX_RISKS] + strengths[:MAX_STRENGTHS]
