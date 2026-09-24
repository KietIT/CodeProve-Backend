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
    assert res["axes"]["hypothesis"] >= 12      # 3 (logged) + 9 (H1 correct) + 5 (before code)
    assert res["axes"]["verification"] >= 18    # 12 (trap caught) + 8 (tested after AI code) of 20
    assert res["axes"]["testing"] > 0
    assert res["axes"]["debugging"] >= 14       # implement: one real failure then fixed -> 16
    assert 0 <= res["overall"] <= 100
    assert res["overall"] > 75   # earn-from-zero rubric still rewards a genuinely strong attempt


def test_gibberish_and_wrong_hypothesis_score_low():
    # User's stress test: typed nonsense (chars added but no test ever passes) and
    # logged a WRONG hypothesis after coding. Must not earn meaningful credit.
    events = [
        _ev("OPEN", 0, {}),
        _ev("CODE_EDIT", 1000, {"charsAdded": 30}),                       # gibberish
        _ev("HYPOTHESIS", 2000, {"proposedBy": "user", "correct": False}),  # wrong, after code
        _ev("RUN", 2500, {"passed": False}),
        _ev("SUBMIT", 3000, {}),
    ]
    res = score_attempt(events, explain_score=0.0)
    assert res["axes"]["understanding"] == 0.0   # no passing run, no real explanation
    assert res["axes"]["hypothesis"] <= 3.0      # wrong hypothesis after coding = habit credit only
    assert res["overall"] < 10


def test_empty_attempt_scores_zero():
    # Nothing done: every observable axis is 0, axes with no opportunity are N/A.
    events = [_ev("OPEN", 0, {}), _ev("SUBMIT", 1000, {})]
    res = score_attempt(events, explain_score=0.0)
    for axis in ("understanding", "hypothesis", "testing"):
        assert res["axes"][axis] == 0.0, f"{axis} should be 0 for an empty attempt"
    for axis in ("prompting", "verification", "debugging"):
        assert res["axes"][axis] is None, f"{axis} should be N/A for an empty attempt"
    assert res["overall"] == 0.0


def test_not_applicable_axes_renormalize():
    events = [_ev("OPEN", 0, {}), _ev("SUBMIT", 1000, {})]
    res = score_attempt(events, explain_score=20.0)
    assert res["axes"]["understanding"] == 18.0   # 0.9 * 20, no passing run
    assert res["not_applicable"] == {
        "prompting": "no_ai_use", "verification": "no_ai_code", "debugging": "no_failure",
    }
    # Active weights .25 (understanding) + .22 (hypothesis) + .10 (testing) = .57.
    assert res["overall"] == round(5 * (0.25 / 0.57) * 18.0, 2)


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

def _solve(fails: int, kind_starter_runs: int = 0) -> list[dict]:
    """A good session (read the problem, correct hypothesis first) that needs
    `fails` real failing runs before passing; optional untouched-starter runs first."""
    ev = [_ev("OPEN", 0, {"problemReadRatio": 1.0}),
          _ev("HYPOTHESIS", 30000, {"proposedBy": "user", "correct": True}),
          _ev("CODE_EDIT", 60000, {"charsAdded": 200})]
    ts = 70000
    for _ in range(kind_starter_runs):
        ev.append(_ev("RUN", ts, {"passed": False, "passRatio": 0.0, "isStarter": True})); ts += 1000
    for _ in range(fails):
        ev.append(_ev("RUN", ts, {"passed": False, "passRatio": 0.5, "isStarter": False})); ts += 1000
    ev.append(_ev("RUN", ts, {"passed": True, "passRatio": 1.0, "isStarter": False}))
    ev.append(_ev("SUBMIT", ts + 1000, {}))
    return ev


def test_first_try_solve_is_not_penalised_for_debugging():
    res = score_attempt(_solve(fails=0), explain_score=18.0)
    assert res["axes"]["debugging"] is None
    assert res["axes"]["prompting"] is None
    assert res["axes"]["verification"] is None
    assert res["axes"]["testing"] == 20.0
    assert res["overall"] > 85


def test_needing_fixes_never_beats_a_clean_first_try():
    clean = score_attempt(_solve(fails=0), explain_score=18.0)
    one_fix = score_attempt(_solve(fails=1), explain_score=18.0)
    three_fixes = score_attempt(_solve(fails=3), explain_score=18.0)
    assert one_fix["axes"]["debugging"] == 16.0
    assert three_fixes["axes"]["debugging"] == 12.0
    assert clean["overall"] > one_fix["overall"] > three_fixes["overall"]


def test_running_the_untouched_starter_cannot_farm_debugging():
    res = score_attempt(_solve(fails=0, kind_starter_runs=3), explain_score=18.0)
    assert res["axes"]["debugging"] is None


def test_regression_after_first_pass_does_not_count():
    events = _solve(fails=0) + [
        _ev("RUN", 90000, {"passed": False, "passRatio": 0.5, "isStarter": False}),
        _ev("RUN", 91000, {"passed": True, "passRatio": 1.0, "isStarter": False}),
    ]
    assert score_attempt(events, explain_score=18.0)["axes"]["debugging"] is None


def test_debug_exercise_always_scores_debugging():
    assert score_attempt(_solve(fails=0), 18.0, exercise_kind="debug")["axes"]["debugging"] == 20.0
    assert score_attempt(_solve(fails=1), 18.0, exercise_kind="debug")["axes"]["debugging"] == 18.0
    never_fixed = [_ev("OPEN", 0, {}), _ev("RUN", 1000, {"passed": False, "passRatio": 0.0, "isStarter": False})]
    assert score_attempt(never_fixed, 0.0, exercise_kind="debug")["axes"]["debugging"] == 0.0


def test_testing_does_not_depend_on_how_many_cases_the_author_wrote():
    two = [_ev("RUN", 100, {"passed": True, "passRatio": 1.0}), _ev("TEST_RUN", 100, {"passed": True, "testCount": 2, "coverage": 1.0})]
    five = [_ev("RUN", 100, {"passed": True, "passRatio": 1.0}), _ev("TEST_RUN", 100, {"passed": True, "testCount": 5, "coverage": 1.0})]
    assert score_attempt(two, 0.0)["axes"]["testing"] == score_attempt(five, 0.0)["axes"]["testing"] == 20.0


def test_verification_scores_testing_ai_code_and_the_trap():
    ai_code = [_ev("PROMPT", 100, {"messageLength": 60, "messageText": "edge case for empty input?"}),
               _ev("AI_REPLY", 200, {"injectedError": False, "aiCode": [{"loc": 5}]})]
    tested = ai_code + [_ev("RUN", 300, {"passed": True, "passRatio": 1.0})]
    assert score_attempt(tested, 0.0)["axes"]["verification"] == 20.0
    assert score_attempt(ai_code, 0.0)["axes"]["verification"] == 0.0

    trap = [_ev("PROMPT", 100, {"messageLength": 60, "messageText": "edge case for empty input?"}),
            _ev("AI_REPLY", 200, {"injectedError": True, "aiCode": [{"loc": 5}]})]
    caught = trap + [_ev("CODE_EDIT", 300, {"charsAdded": 5}), _ev("RUN", 400, {"passed": True, "passRatio": 1.0}),
                     _ev("SUBMIT", 500, {})]
    missed = trap + [_ev("RUN", 400, {"passed": True, "passRatio": 1.0}), _ev("SUBMIT", 500, {})]
    assert score_attempt(caught, 0.0)["axes"]["verification"] == 20.0
    assert score_attempt(missed, 0.0)["axes"]["verification"] == 0.0   # 8/20*20 - 10, clamped


def test_text_only_ciel_use_makes_verification_na_but_scores_prompting():
    events = [_ev("PROMPT", 100, {"messageLength": 60, "messageText": "what is the expected output format?"}),
              _ev("AI_REPLY", 200, {"injectedError": False, "aiCode": []})]
    res = score_attempt(events, 0.0)
    assert res["axes"]["prompting"] is not None
    assert res["axes"]["verification"] is None


def test_testing_uses_the_full_suite_at_submit_over_runs():
    events = [_ev("RUN", 100, {"passed": True, "passRatio": 1.0}),   # visible tests only
              _ev("SUBMIT_TESTS", 200, {"passRatio": 0.5, "passed": 4, "total": 8})]
    assert score_attempt(events, 0.0)["axes"]["testing"] == 10.0


def test_testing_falls_back_to_the_last_run_without_a_submit_suite():
    events = [_ev("RUN", 100, {"passed": True, "passRatio": 1.0})]
    assert score_attempt(events, 0.0)["axes"]["testing"] == 20.0
