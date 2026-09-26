"""Scoring engine v2 (P1.4): the rubric levels turned into a report.

Each axis gets a level on the rating guide's 0-3 scale from `rubric`, and a
score of 20 x level / 3 so reports keep their 0-20 columns. An axis the
session had no chance to show is N/A (excluded from `overall`, as in v1). An
axis that should be scored but whose judge gave no verdict ("unrated") falls
back to v1's score rather than being dropped, so a judge outage never turns a
weak axis into a missing one. The v1 integrity multiplier scales the scores;
the levels keep describing what was observed.
"""
from app.features.scoring import rubric
from app.features.scoring.engine import NA_REASONS, WEIGHTS, clamp, score_attempt
from app.features.scoring.evidence import Evidence

AXES = ("understanding", "hypothesis", "prompting", "verification", "testing", "debugging")
_INDICATORS = {
    "understanding": rubric.understanding,
    "hypothesis": rubric.hypothesis,
    "prompting": rubric.prompting,
    "verification": rubric.verification,
    "testing": rubric.testing,
    "debugging": rubric.debugging,
}


def display_level(level: float | None) -> int | None:
    """Round half up (2.5 -> 3): the level shown to users."""
    return None if level is None else int(level + 0.5)


def score_attempt_v2(ev: Evidence, explain_score: float | None) -> dict:
    v1 = score_attempt(ev.events, explain_score=explain_score, exercise_kind=ev.exercise_kind)
    mult = v1["integrity_multiplier"]
    raw: dict[str, float | None] = {}
    levels: dict[str, int | None] = {}
    evidence: dict[str, dict] = {}
    not_applicable: dict[str, str] = {}
    for axis in AXES:
        indicator = _INDICATORS[axis](ev)
        evidence[axis] = {"evidence": indicator.evidence, "reason": indicator.reason}
        if indicator.level is not None:
            raw[axis] = 20 * indicator.level / 3
            levels[axis] = display_level(indicator.level)
        elif indicator.reason == "unrated":
            # Scoreable but the judge gave nothing: stand in with v1 (explain score for understanding).
            fallback = clamp(0, 20, explain_score or 0.0) if axis == "understanding" else v1["raw_axes"][axis]
            raw[axis] = fallback
            levels[axis] = display_level(3 * fallback / 20) if fallback is not None else None
        else:
            raw[axis] = None
            levels[axis] = None
            not_applicable[axis] = NA_REASONS.get(axis, indicator.reason)
    axes = {a: (round(v * mult, 2) if v is not None else None) for a, v in raw.items()}
    active = {a: v for a, v in axes.items() if v is not None}
    total = sum(WEIGHTS[a] for a in active)
    overall = round(5 * sum(WEIGHTS[a] / total * v for a, v in active.items()), 2) if total else 0.0
    return {
        "axes": axes,
        "overall": clamp(0, 100, overall),
        "features": v1["features"],
        "integrity_multiplier": mult,
        "not_applicable": not_applicable,
        "levels": levels,
        "evidence": evidence,
        "engine": "v2",
    }
