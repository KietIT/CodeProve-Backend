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
    assert res["axes"]["hypothesis"] >= 12      # base 8 + 4 (H1)
    assert res["axes"]["verification"] >= 18    # base 12 + 8 (V1 caught)
    assert res["axes"]["testing"] > 0
    assert res["axes"]["debugging"] >= 14       # base 8 + 6 (one fix cycle)
    assert 0 <= res["overall"] <= 100
    assert res["overall"] > 60


def test_disabled_axes_renormalize():
    events = [_ev("OPEN", 0, {}), _ev("SUBMIT", 1000, {})]
    res = score_attempt(events, explain_score=0.0, testing_enabled=False, debugging_enabled=False)
    assert res["axes"]["testing"] is None
    assert res["axes"]["debugging"] is None
    assert 0 <= res["overall"] <= 100


def test_no_plan_caps_hypothesis():
    events = [_ev("OPEN", 0, {}), _ev("CODE_EDIT", 1000, {}), _ev("SUBMIT", 2000, {})]
    res = score_attempt(events, explain_score=0.0)
    assert res["axes"]["hypothesis"] <= 10   # H3 no-plan cap
