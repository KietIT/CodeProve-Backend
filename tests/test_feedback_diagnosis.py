"""Diagnosis (P1.5, Task 1): rubric v2 evidence -> ranked findings."""
from app.features.feedback.diagnosis import MAX_RISKS, MAX_STRENGTHS, diagnose
from app.features.scoring.engine_v2 import score_attempt_v2
from app.features.scoring.evidence import Evidence, Reply, Snapshot

MIN = 60_000
STARTER = "def two_sum(nums, target):\n    pass"
AI_CODE = ("def two_sum(nums, target):\n    seen = {}\n    for i, n in enumerate(nums):\n"
           "        if target - n in seen:\n            return [seen[target - n], i]\n        seen[n] = i")


def e(type_, minute, payload=None, flags=None):
    return {"type": type_, "ts": int(minute * MIN), "payload": payload or {}, "integrity_flags": flags or []}


def suite(passed, total, visible_passed, visible_total=2, failed=()):
    return e("SUBMIT_TESTS", 20, {"passed": passed, "total": total, "visiblePassed": visible_passed,
                                  "visibleTotal": visible_total, "failedCategories": list(failed)})


def run(minute, ratio, starter=False):
    return e("RUN", minute, {"passed": ratio == 1.0, "passRatio": ratio, "isStarter": starter})


def explain(level):
    return e("JUDGE", 25, {"kind": "explain", "levels": [level], "evidence": ["vì dict tra O(1)"]})


def hyp(minute, level):
    return e("HYPOTHESIS", minute, {"proposedBy": "user", "correct": True, "level": level,
                                    "levelEvidence": "dict, O(n)"})


def findings(*events, kind="implement", replies=(), snapshots=(), explain_score=12):
    ev = Evidence(exercise_kind=kind, events=sorted(events, key=lambda x: x["ts"]), replies=list(replies),
                  snapshots=list(snapshots))
    return diagnose(score_attempt_v2(ev, explain_score), ev)


def codes(found):
    return [f.code for f in found]


def test_a_strong_first_try_solve_gives_strengths_only():
    out = findings(hyp(1, 3), e("CODE_EDIT", 2), run(3, 1.0), suite(8, 8, 2), explain(3))
    assert all(f.kind == "strength" for f in out)
    assert codes(out) == ["explain_strong", "hypothesis_strong"]  # the 2 highest-weight strengths


def test_weak_understanding_and_missing_hypothesis():
    out = findings(e("CODE_EDIT", 2), run(3, 1.0), suite(8, 8, 2), explain(0))
    risks = [f for f in out if f.kind == "risk"]
    assert codes(risks) == ["explain_missing", "no_hypothesis"]
    assert risks[0].severity == "high" and risks[1].severity == "medium"


def test_hidden_edge_failures_carry_the_failed_categories():
    out = findings(hyp(1, 2), e("CODE_EDIT", 2), run(3, 1.0), suite(5, 8, 2, failed=("boundary", "edge")),
                   explain(2))
    edge = next(f for f in out if f.code == "hidden_edge_failed")
    assert edge.params == {"failed_categories": ["boundary", "edge"]} and edge.severity == "medium"


def test_never_running_tests_is_high():
    out = findings(hyp(1, 2), e("CODE_EDIT", 2), suite(1, 8, 0), explain(2))
    assert "never_ran_tests" in codes(out)


def test_submitting_with_visible_failures_reports_the_counts():
    out = findings(hyp(1, 2), e("CODE_EDIT", 2), run(3, 0.5), suite(5, 8, 1), explain(2))
    failing = next(f for f in out if f.code == "submitted_failing")
    assert failing.params == {"passed": 5, "total": 8}


def test_asking_for_the_solution_outranks_vague_prompts():
    out = findings(hyp(1, 2), e("CODE_EDIT", 2), run(3, 1.0), suite(8, 8, 2), explain(2),
                   e("PROMPT", 1.5), e("PROMPT", 1.6),
                   e("JUDGE", 26, {"kind": "prompts", "levels": [0, 1], "evidence": ["viết code", "?"],
                                   "asks_for_solution": [True, False]}))
    assert "asked_for_solution" in codes(out) and "prompts_vague" not in codes(out)
    assert next(f for f in out if f.code == "asked_for_solution").params == {"count": 1}


def test_verification_regressions_from_the_golden_set():
    replies = [Reply(prompt="write it", text=f"```python\n{AI_CODE}\n```", at_ms=MIN, injected=False)]
    snaps = [Snapshot(1, STARTER, 0), Snapshot(2, AI_CODE, 2 * MIN)]
    base = (hyp(0.5, 2), e("CODE_EDIT", 2), run(3, 1.0), explain(2), e("PROMPT", 0.9))
    # sim-02: pasted unchanged, passed.
    assert "pasted_ai_unchecked" in codes(findings(*base, suite(8, 8, 2), replies=replies, snapshots=snaps))
    # sim-18: pasted unchanged, failed.
    failing = findings(*base, suite(2, 8, 1), replies=replies, snapshots=snaps)
    assert "pasted_ai_failing" in codes(failing)


def test_debugging_findings():
    debug = dict(kind="debug")
    # sim-19: visible pass, hidden edge fails.
    partial = findings(hyp(1, 2), run(2, 1.0, starter=True), e("CODE_EDIT", 3), run(4, 1.0),
                       suite(4, 7, 2, failed=("edge",)), explain(2), **debug)
    assert next(f for f in partial if f.code == "partial_fix").params == {"failed_categories": ["edge"]}
    unfixed = findings(hyp(1, 2), e("CODE_EDIT", 3), run(4, 0.5), suite(3, 7, 1), explain(2), **debug)
    assert "bug_not_fixed" in codes(unfixed)
    trial = findings(hyp(1, 2), e("CODE_EDIT", 3), *[run(m, 0.5) for m in (4, 5, 6, 7)], run(8, 1.0),
                     suite(7, 7, 2), explain(2), **debug)
    assert next(f for f in trial if f.code == "trial_and_error").params == {"failing_runs": 4}


def test_not_applicable_axes_give_no_finding():
    out = findings(hyp(1, 2), e("CODE_EDIT", 2), run(3, 1.0), suite(8, 8, 2), explain(2))
    assert not [f for f in out if f.axis in ("prompting", "verification", "debugging")]


def test_integrity_flags_are_a_high_risk():
    out = findings(hyp(1, 2), e("CODE_EDIT", 2), e("BURST_PASTE", 2.5), run(3, 1.0), suite(8, 8, 2), explain(2))
    flags = next(f for f in out if f.code == "integrity_flags")
    assert flags.severity == "high" and flags.params["paste"] == 1


def test_the_list_is_trimmed_and_ranked():
    out = findings(e("CODE_EDIT", 2), suite(0, 8, 0), explain(0), e("BURST_PASTE", 2.5),
                   e("PROMPT", 1), e("JUDGE", 26, {"kind": "prompts", "levels": [0], "asks_for_solution": [True]}))
    risks = [f for f in out if f.kind == "risk"]
    assert len(risks) == MAX_RISKS and all(f.severity == "high" for f in risks)
    assert risks[0].code == "integrity_flags"  # a compromised session is said first
    assert len([f for f in out if f.kind == "strength"]) <= MAX_STRENGTHS
