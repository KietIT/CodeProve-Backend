import math

from app.features.scoring.engine import WEIGHTS
from app.features.scoring.engine_v2 import score_attempt_v2
from app.features.scoring.evidence import Evidence

MIN = 60_000


def e(type_: str, minute: float, payload: dict | None = None, flags: list[str] | None = None) -> dict:
    return {"type": type_, "ts": int(minute * MIN), "payload": payload or {}, "integrity_flags": flags or []}


def session(*extra: dict, kind: str = "implement") -> Evidence:
    events = [
        e("OPEN", 0),
        e("HYPOTHESIS", 1, {"proposedBy": "user", "correct": True, "level": 3, "levelEvidence": "dict, O(n)"}),
        e("CODE_EDIT", 2, {"charsAdded": 80}),
        e("RUN", 3, {"passed": True, "passRatio": 1.0, "isStarter": False}),
        e("SUBMIT", 4),
        e("SUBMIT_TESTS", 4, {"passed": 8, "total": 8, "visiblePassed": 2, "visibleTotal": 2, "passRatio": 1.0}),
        e("JUDGE", 5, {"kind": "explain", "levels": [2], "evidence": ["dict lookups"]}),
        *extra,
    ]
    return Evidence(exercise_kind=kind, events=sorted(events, key=lambda x: x["ts"]))


def test_axes_are_20_times_the_level_over_3_and_na_axes_are_excluded():
    result = score_attempt_v2(session(), explain_score=14)
    assert result["levels"] == {"understanding": 2, "hypothesis": 3, "prompting": None, "verification": None,
                                "testing": 3, "debugging": None}
    assert result["axes"]["understanding"] == round(20 * 2 / 3, 2)
    assert result["axes"]["hypothesis"] == 20 and result["axes"]["testing"] == 20
    assert result["not_applicable"] == {"prompting": "no_ai_use", "verification": "no_ai_code",
                                        "debugging": "no_failure"}
    active = {a: v for a, v in result["axes"].items() if v is not None}
    total = sum(WEIGHTS[a] for a in active)
    assert math.isclose(result["overall"], round(5 * sum(WEIGHTS[a] / total * v for a, v in active.items()), 2))
    assert result["evidence"]["hypothesis"] == {"evidence": "dict, O(n)", "reason": ""}
    assert result["engine"] == "v2"


def test_an_unrated_axis_falls_back_to_the_v1_score():
    # The prompt judge failed: prompting is not N/A (the student did ask), so v1's score stands in.
    result = score_attempt_v2(session(e("PROMPT", 1.5, {"messageText": "why does n = 0 fail?", "messageLength": 20}),
                                      e("AI_REPLY", 1.6, {"aiCode": []})), explain_score=14)
    assert result["axes"]["prompting"] is not None
    assert result["evidence"]["prompting"]["reason"] == "unrated"
    assert "prompting" not in result["not_applicable"]


def test_an_unrated_understanding_uses_the_explain_score():
    ev = session()
    ev.events = [x for x in ev.events if x["type"] != "JUDGE"]
    result = score_attempt_v2(ev, explain_score=15)
    assert result["axes"]["understanding"] == 15.0 and result["levels"]["understanding"] == 2


def test_the_integrity_multiplier_still_applies():
    clean = score_attempt_v2(session(), explain_score=14)
    pasted = score_attempt_v2(session(e("BURST_PASTE", 2.5), e("BURST_PASTE", 2.6)), explain_score=14)
    assert pasted["integrity_multiplier"] < 1.0
    assert pasted["axes"]["testing"] < clean["axes"]["testing"]
    # Levels describe the observed behaviour; the multiplier only scales the score.
    assert pasted["levels"]["testing"] == 3


def test_debug_exercises_always_score_debugging():
    unfixed = session(kind="debug")
    for x in unfixed.events:
        if x["type"] == "SUBMIT_TESTS":
            x["payload"] = {"passed": 3, "total": 7, "visiblePassed": 1, "visibleTotal": 2}
    result = score_attempt_v2(unfixed, explain_score=14)
    assert result["levels"]["debugging"] == 0 and result["axes"]["debugging"] == 0
