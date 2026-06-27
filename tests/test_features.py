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
