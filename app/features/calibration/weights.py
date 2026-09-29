"""Axis weight selection on the golden set (P1.7).

Recomputes every session's overall from the engine's axis scores under each
candidate weight set (with the engine's own `weighted_overall`), and measures
agreement with the raters' holistic overall level: Spearman (primary), ICC(2,1)
between the engine's tier and the human mean level, and exact tier agreement.
Pure Python, like `agreement.py` and `ahp.py`.
"""
import math
import random
import statistics

from app.features.attempts.scoring_service import tier_for
from app.features.calibration import ahp
from app.features.calibration.agreement import icc2, spearman
from app.features.calibration.analyze import OVERALL_LEVELS, Dump, ahp_section
from app.features.scoring.engine import WEIGHTS, weighted_overall

AXES = ahp.AXES
TIERS = ("Emerging", "Developing", "Strong", "Exceptional")  # tier_for's names, lowest first = level 0-3


def candidates(ahp_answers: dict[str, dict]) -> dict[str, dict[str, float]]:
    """The fixed weight sets: current, equal, and the team's AHP (all members,
    and consistent members only when that differs)."""
    sets = {"current": dict(WEIGHTS), "equal": {a: 1 / len(AXES) for a in AXES}}
    section = ahp_section(ahp_answers)
    if section["group_weights"]:
        sets["ahp"] = section["group_weights"]
    if section["group_consistent_weights"]:
        sets["ahp_consistent"] = section["group_consistent_weights"]
    return sets


def human_overall(dump: Dump) -> dict[str, float]:
    """Mean overall level (0-3) per session over the raters who gave one."""
    levels: dict[str, list[int]] = {}
    for sessions in dump.ratings.values():
        for sid, rating in sessions.items():
            if rating.get("overall") in OVERALL_LEVELS:
                levels.setdefault(sid, []).append(OVERALL_LEVELS.index(rating["overall"]))
    return {sid: statistics.mean(values) for sid, values in levels.items()}


def overalls(engine: dict[str, dict], weights: dict[str, float]) -> dict[str, float]:
    return {sid: weighted_overall(entry["axes"], weights) for sid, entry in engine.items()}


def tier_level(overall: float) -> int:
    return TIERS.index(tier_for(overall))


def _half_up(x: float) -> int:
    return math.floor(x + 0.5)


def evaluate(overall_by_session: dict[str, float], human: dict[str, float]) -> dict:
    sessions = sorted(set(overall_by_session) & set(human))
    engine = [overall_by_session[s] for s in sessions]
    people = [human[s] for s in sessions]
    tiers = [tier_level(o) for o in engine]
    icc, _ = icc2([[float(t), h] for t, h in zip(tiers, people)]) if len(sessions) >= 2 else (math.nan, math.nan)
    return {
        "spearman": spearman(engine, people) if len(sessions) >= 3 else math.nan,
        "icc": icc,
        "tier_exact": sum(t == _half_up(h) for t, h in zip(tiers, people)) / len(sessions) if sessions else math.nan,
        "n": len(sessions),
    }


def bootstrap_delta(a: dict[str, float], b: dict[str, float], human: dict[str, float],
                    samples: int = 2000, seed: int = 0) -> tuple[float, float, float]:
    """Paired bootstrap of Spearman(a) - Spearman(b): (mean, 2.5th, 97.5th percentile).
    Resamples sessions, so both sets are always compared on the same sample."""
    sessions = sorted(set(a) & set(b) & set(human))
    rng = random.Random(seed)
    deltas = []
    for _ in range(samples):
        pick = [rng.choice(sessions) for _ in sessions]
        people = [human[s] for s in pick]
        delta = spearman([a[s] for s in pick], people) - spearman([b[s] for s in pick], people)
        if not math.isnan(delta):  # a sample where one side is constant has no rank correlation
            deltas.append(delta)
    if not deltas:
        return math.nan, math.nan, math.nan
    deltas.sort()
    return (round(statistics.mean(deltas), 6), round(deltas[int(0.025 * (len(deltas) - 1))], 6),
            round(deltas[int(0.975 * (len(deltas) - 1))], 6))
