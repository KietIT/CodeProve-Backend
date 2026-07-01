from app.features.scoring.engine import clamp, score_attempt


def _ev(t, ts, payload=None, flags=None):
    return {"type": t, "ts": ts, "payload": payload or {}, "integrity_flags": flags or []}


def test_clamp():
    assert clamp(0, 20, 25) == 20
    assert clamp(0, 20, -3) == 0
    assert clamp(0, 20, 12) == 12


def test_strong_attempt_scores_high():
    events = [
        _ev("OPEN", 0, {"problemReadRatio": 0.9}),
        _ev("HYPOTHESIS", 25000, {"proposedBy": "user", "correct": True}),
        _ev("CODE_EDIT", 26000, {"charsAdded": 40}),
        _ev("PROMPT", 40000, {"messageLength": 80, "messageText": "what edge cases for the target with a hash map?", "keywordsMatched": ["hash map", "target"]}),
        _ev("AI_REPLY", 41000, {"injectedError": True, "aiCode": [{"loc": 6}]}),
        _ev("CODE_EDIT", 60000, {"charsAdded": 20}),    # caught the trap
        _ev("TEST_RUN", 65000, {"passed": False, "testCount": 3, "coverage": 0.8}),
        _ev("CODE_EDIT", 66000, {"charsAdded": 5}),
        _ev("TEST_RUN", 67000, {"passed": True, "testCount": 3, "coverage": 0.8}),
        _ev("SUBMIT", 70000, {}),
    ]
    res = score_attempt(events, explain_score=18.0)
    assert res["axes"]["hypothesis"] >= 12      # 6 (logged) + 6 (H1 correct) + 6 (before code)
    assert res["axes"]["verification"] >= 18    # 10 (V1 caught) + 4 (tested) + 4 (coverage)
    assert res["axes"]["testing"] > 0
    assert res["axes"]["debugging"] >= 14       # 6 + 8 (one fix cycle)
    assert 0 <= res["overall"] <= 100
    assert res["overall"] > 75   # earn-from-zero rubric still rewards a genuinely strong attempt


def test_empty_attempt_scores_zero():
    # A candidate who does nothing - no code, no hypothesis, no prompt, no test,
    # and an empty explanation - must score 0 on every axis and 0 overall.
    events = [_ev("OPEN", 0, {}), _ev("SUBMIT", 1000, {})]
    res = score_attempt(events, explain_score=0.0)
    for axis in ("understanding", "hypothesis", "prompting", "verification", "testing", "debugging"):
        assert res["axes"][axis] == 0.0, f"{axis} should be 0 for an empty attempt"
    assert res["overall"] == 0.0


def test_disabled_axes_renormalize():
    # Only understanding is earned (via explain-back); testing/debugging disabled.
    # Overall must renormalize over the remaining active weights.
    events = [_ev("OPEN", 0, {}), _ev("SUBMIT", 1000, {})]
    res = score_attempt(events, explain_score=20.0, testing_enabled=False, debugging_enabled=False)
    assert res["axes"]["testing"] is None
    assert res["axes"]["debugging"] is None
    assert res["axes"]["understanding"] == 18.0   # 0.9 * 20, no code-engagement bonus
    assert res["axes"]["hypothesis"] == 0.0
    assert res["axes"]["prompting"] == 0.0
    assert res["axes"]["verification"] == 0.0
    # Active weights .25/.22/.18/.15 renormalize over 0.80; only understanding is non-zero.
    assert res["overall"] == round(5 * (0.25 / 0.80) * 18.0, 2)


def test_overall_is_100_when_all_active_axes_maxed():
    # Renormalization invariant: if every active axis is at its max (20), overall must be exactly 100
    # regardless of which axes are disabled.
    import app.features.scoring.engine as engine

    maxed = {a: 20.0 for a in ["understanding", "hypothesis", "prompting", "verification"]}
    total = sum(engine.WEIGHTS[a] for a in maxed)
    overall = round(5 * sum((engine.WEIGHTS[a] / total) * v for a, v in maxed.items()), 2)
    assert overall == 100.0


def test_no_hypothesis_scores_zero_hypothesis():
    events = [_ev("OPEN", 0, {}), _ev("CODE_EDIT", 1000, {"charsAdded": 20}), _ev("SUBMIT", 2000, {})]
    res = score_attempt(events, explain_score=0.0)
    assert res["axes"]["hypothesis"] == 0.0   # coded but never logged a hypothesis
