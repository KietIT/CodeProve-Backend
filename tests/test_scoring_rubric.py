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
