from app.features.scoring.evidence import Evidence
from app.features.scoring.rubric import hypothesis, prompting, understanding


def ev(*events: tuple, kind: str = "implement") -> Evidence:
    """Evidence from (type, minute, payload) triples."""
    return Evidence(exercise_kind=kind, events=sorted(
        ({"type": t, "ts": int(m * 60_000), "payload": p, "integrity_flags": []} for t, m, p in events),
        key=lambda e: e["ts"]))


def hyp(minute, level=None, correct=True, text="plan", **extra):
    return ("HYPOTHESIS", minute, {"proposedBy": "user", "correct": correct, "text": text, "level": level,
                                   "levelEvidence": text, **extra})


# ---------- Understanding ----------

def test_understanding_is_the_mean_explain_back_level():
    out = understanding(ev(("JUDGE", 9, {"kind": "explain", "levels": [3, 2], "evidence": ["vì sao", "cái gì"]})))
    assert out.level == 2.5 and "vì sao" in out.evidence


def test_understanding_ignores_unrated_answers_and_is_unknown_without_any():
    assert understanding(ev(("JUDGE", 9, {"kind": "explain", "levels": [None, 1], "evidence": ["", "x"]}))).level == 1
    assert understanding(ev(("JUDGE", 9, {"kind": "explain", "levels": [None], "evidence": [""]}))).level is None
    assert understanding(ev()).level is None


def test_understanding_uses_the_latest_explain_verdict():
    out = understanding(ev(("JUDGE", 9, {"kind": "explain", "levels": [0]}),
                           ("JUDGE", 10, {"kind": "explain", "levels": [3]})))
    assert out.level == 3


# ---------- Hypothesis ----------

def test_no_hypothesis_is_level_0():
    out = hypothesis(ev(("CODE_EDIT", 2, {"charsAdded": 40})))
    assert out.level == 0 and out.reason == "no_hypothesis"


def test_level_3_needs_the_hypothesis_before_the_first_code_edit():
    before = hypothesis(ev(hyp(1, level=3), ("CODE_EDIT", 2, {})))
    after = hypothesis(ev(("CODE_EDIT", 1, {}), hyp(2, level=3)))
    assert before.level == 3
    assert after.level == 2 and after.reason == "after_code"


def test_the_best_hypothesis_counts_and_ai_hypotheses_do_not():
    out = hypothesis(ev(hyp(1, level=1), hyp(2, level=2, text="dict lưu phần bù"),
                        ("HYPOTHESIS", 3, {"proposedBy": "ai", "level": 3})))
    assert out.level == 2 and out.evidence == "dict lưu phần bù"


def test_hypotheses_without_a_level_fall_back_to_the_verdict_capped_at_2():
    # Sessions logged before rubric v2 only have correct/incorrect (rating guide: at most level 2).
    assert hypothesis(ev(("HYPOTHESIS", 1, {"proposedBy": "user", "correct": True}))).level == 2
    assert hypothesis(ev(("HYPOTHESIS", 1, {"proposedBy": "user", "correct": False}))).level == 1


# ---------- Prompting ----------

def test_prompting_is_not_applicable_without_prompts():
    assert prompting(ev()).level is None
    assert prompting(ev()).reason == "no_ai_use"


def test_prompting_is_the_median_prompt_level():
    out = prompting(ev(("PROMPT", 1, {}), ("PROMPT", 2, {}), ("PROMPT", 3, {}),
                       ("JUDGE", 9, {"kind": "prompts", "levels": [0, 3, 2], "evidence": ["a", "b", "c"]})))
    assert out.level == 2 and out.evidence == "c"


def test_one_specific_prompt_reaches_level_3():
    # Asking Ciel well must never score worse than not asking (P0 incentive fix).
    out = prompting(ev(("PROMPT", 1, {}), ("JUDGE", 9, {"kind": "prompts", "levels": [3], "evidence": ["x"]})))
    assert out.level == 3


def test_prompts_without_a_verdict_are_unrated_not_zero():
    out = prompting(ev(("PROMPT", 1, {})))
    assert out.level is None and out.reason == "unrated"


# ---------- Debugging: debug exercises with the locate step (P2.2) ----------

from app.features.scoring.rubric import debugging  # noqa: E402

REGIONS = [[3]]


def debug_ev(*events: tuple, regions=REGIONS) -> Evidence:
    out = ev(*events, kind="debug")
    out.debug_regions = regions
    return out


def locate(lines, hints=0, skipped=False, minute=1):
    return ("LOCATE", minute, {"lines": lines, "reason": "r", "skipped": skipped, "hintsUsed": hints})


def explained(level):
    return ("JUDGE", 20, {"kind": "locate", "level": level, "evidence": "stops before n"})


def run(minute, ratio):
    return ("RUN", minute, {"passed": ratio == 1.0, "passRatio": ratio, "isStarter": False})


def suite(passed, total, visible_passed=2, visible_total=2):
    return ("SUBMIT_TESTS", 10, {"passed": passed, "total": total, "passRatio": passed / total,
                                 "visiblePassed": visible_passed, "visibleTotal": visible_total})


def test_a_perfect_debug_session_is_level_3_on_every_part():
    out = debugging(debug_ev(locate([3]), explained(3), run(3, 1.0), suite(7, 7)))
    assert out.level == 3 and out.reason == "fixed"
    assert out.parts == {"located": 3, "explained": 3, "fixed": 3, "efficiency": 3,
                         "hit": [True], "hints_used": 0, "skipped": False}


def test_located_level_follows_hints_and_partial_hits():
    def located(*events, regions=REGIONS):
        return debugging(debug_ev(*events, explained(2), suite(7, 7), regions=regions)).parts["located"]

    assert located(locate([3], hints=1)) == 2
    assert located(locate([3], hints=2)) == 1
    assert located(locate([4])) == 0
    two = [[7], [9]]
    assert located(locate([7]), regions=two) == 2                # one of two issues, no hint
    assert located(locate([7], hints=1), regions=two) == 1
    assert located(locate([7, 9], hints=1), regions=two) == 2


def test_fixed_and_efficiency_levels():
    parts = debugging(debug_ev(locate([3]), explained(3), run(3, 0.5), run(4, 0.5), run(5, 1.0),
                               suite(7, 7))).parts
    assert parts["fixed"] == 3 and parts["efficiency"] == 2      # 2 failing runs before the fix
    hidden_fail = debugging(debug_ev(locate([3]), explained(3), run(3, 1.0), suite(6, 7))).parts
    assert hidden_fail["fixed"] == 2 and hidden_fail["efficiency"] is None  # efficiency only when fixed
    some_visible = debugging(debug_ev(locate([3]), explained(3), run(3, 0.5), suite(3, 7, visible_passed=1)))
    assert some_visible.parts["fixed"] == 1 and some_visible.reason == "not_fixed"
    none_visible = debugging(debug_ev(locate([3]), explained(3), run(3, 0.0), suite(0, 7, visible_passed=0)))
    assert none_visible.parts["fixed"] == 0


def test_the_axis_is_the_mean_of_the_applicable_parts():
    out = debugging(debug_ev(locate([3], hints=1), explained(1), run(3, 1.0), suite(6, 7)))
    # located 2, explained 1, fixed 2, efficiency N/A
    assert out.level == (2 + 1 + 2) / 3 and out.reason == "partially_fixed"


def test_a_skip_scores_located_and_explained_0():
    out = debugging(debug_ev(locate([], skipped=True), explained(0), run(3, 1.0), suite(7, 7)))
    assert out.parts["located"] == 0 and out.parts["explained"] == 0 and out.parts["skipped"] is True
    assert out.level == (0 + 0 + 3 + 3) / 4


def test_an_unrated_explanation_leaves_that_part_out():
    out = debugging(debug_ev(locate([3]), explained(None), run(3, 1.0), suite(7, 7)))
    assert out.parts["explained"] is None and out.level == 3


def test_without_a_locate_event_the_p14_indicator_is_unchanged():
    out = debugging(debug_ev(run(3, 0.5), run(4, 1.0), suite(7, 7)))
    assert out.level == 3 and out.reason == "fixed" and out.parts is None
    unfixed = debugging(debug_ev(run(3, 0.5), suite(3, 7, visible_passed=1)))
    assert unfixed.level == 0 and unfixed.reason == "not_fixed"
