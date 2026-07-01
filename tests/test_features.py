from app.features.scoring.features import compute_features
from app.features.scoring.text_utils import cluster_near_duplicates, similar


def test_similar_and_clusters():
    assert similar("explain the time complexity", "explain the time complexity") == 1.0
    dups = ["fix my loop please", "fix my loop please", "fix my loop please", "totally different text"]
    assert cluster_near_duplicates(dups, 0.85) == 1


def _ev(t, ts, payload=None, flags=None):
    return {"type": t, "ts": ts, "payload": payload or {}, "integrity_flags": flags or []}


def test_prompting_and_verification_features():
    events = [
        _ev("OPEN", 0, {"problemReadRatio": 0.8}),
        _ev("PROMPT", 30000, {"messageLength": 10, "keywordsMatched": []}),     # lazy (P1)
        _ev("AI_REPLY", 30500, {"injectedError": True, "aiCode": [{"loc": 25}]}),
        _ev("CODE_EDIT", 60000, {"charsAdded": 40}),                            # refine after -> trap caught
        _ev("SUBMIT", 70000, {}),
    ]
    f = compute_features(events, explain_score=15.0)
    assert f.p1_hits == 1
    assert f.prompt_count == 1
    assert f.has_v1 is True            # injected error then edited before submit
    assert f.first_prompt_delay_ms == 30000


def test_hypothesis_and_debugging_features():
    events = [
        _ev("OPEN", 0),
        _ev("HYPOTHESIS", 100, {"proposedBy": "user", "correct": True}),
        _ev("HYPOTHESIS", 150, {"proposedBy": "ai"}),
        _ev("CODE_EDIT", 200, {"charsAdded": 10}),
        _ev("RUN", 300, {"passed": False}),
        _ev("CODE_EDIT", 350, {"charsAdded": 5}),
        _ev("RUN", 400, {"passed": True}),
    ]
    f = compute_features(events, explain_score=0.0)
    assert f.h1_count == 1
    assert f.h2_count == 1
    assert f.has_hypothesis_before_code is True   # hypothesis at 100 precedes first code at 200
    assert f.d1_count == 1                        # one fail -> pass cycle


def test_testing_features():
    events = [
        _ev("OPEN", 0),
        _ev("TEST_RUN", 100, {"passed": False, "testCount": 4, "coverage": 0.5}),
        _ev("TEST_RUN", 200, {"passed": True, "testCount": 4, "coverage": 0.85}),
    ]
    f = compute_features(events, explain_score=0.0)
    assert f.has_test_run is True
    assert f.t1_count == 4
    assert f.best_coverage == 0.85


def test_paste_blind_and_integrity():
    events = [
        _ev("OPEN", 0),
        _ev("PROMPT", 100, {"messageLength": 50}),
        _ev("AI_REPLY", 200, {"aiCode": [{"loc": 60}]}),   # >=50 loc, no edit after -> paste-blind
        _ev("PASTE", 300, {"length": 200}, ["BURST_PASTE"]),
        _ev("FOCUS_LOST", 400),
        _ev("SUBMIT", 500),
    ]
    f = compute_features(events, explain_score=0.0)
    assert f.has_v3 is True
    assert f.paste_flags == 1
    assert f.focus_lost == 1
    assert f.integrity_flag_total == 2


def test_integrity_uses_specific_anticheat_events():
    events = [
        _ev("OPEN", 0),
        _ev("TAB_HIDDEN", 100),
        _ev("TAB_VISIBLE", 200),
        _ev("WINDOW_BLUR", 300),
        _ev("WINDOW_FOCUS", 400),
        _ev("FULLSCREEN_EXIT", 500),
        _ev("FULLSCREEN_ENTER", 600),
        _ev("COPY", 700, {"length": 10}),
        _ev("CUT", 800, {"length": 5}),
        _ev("PASTE", 900, {"length": 20}),
        _ev("BURST_PASTE", 1000, {"length": 200}, ["BURST_PASTE"]),
    ]
    f = compute_features(events, explain_score=0.0)
    assert f.tab_hidden == 1
    assert f.window_blur == 1
    assert f.fullscreen_exits == 1
    assert f.copy_count == 1
    assert f.cut_count == 1
    assert f.paste_count == 1
    assert f.paste_flags == 1
    assert f.integrity_flag_total == 4


def test_prompting_clusters_and_keywords():
    dup = {"messageLength": 50, "keywordsMatched": ["a", "b"], "messageText": "fix my loop please"}
    events = [
        _ev("OPEN", 0),
        _ev("PROMPT", 1, dict(dup)),
        _ev("PROMPT", 2, dict(dup)),
        _ev("PROMPT", 3, dict(dup)),
    ]
    f = compute_features(events, explain_score=0.0)
    assert f.p2_clusters == 1          # three near-duplicate prompts -> one cluster
    assert f.p3_hits == 3              # two keywords each (capped at 4)
    assert f.p4_hits == 3              # none mention a constraint/format hint
    assert f.p1_hits == 0             # length 50 is not lazy


def test_features_are_timestamp_ordered_not_list_ordered():
    # Events deliberately out of list order; derivations must use ts order.
    events = [
        _ev("RUN", 400, {"passed": True}),
        _ev("OPEN", 0),
        _ev("RUN", 300, {"passed": False}),
        _ev("PROMPT", 200, {"messageLength": 5}),
    ]
    f = compute_features(events, explain_score=0.0)
    assert f.first_prompt_delay_ms == 200    # 200 - 0
    assert f.d1_count == 1                   # fail(300) -> pass(400) once ts-ordered
    assert f.p1_hits == 1
