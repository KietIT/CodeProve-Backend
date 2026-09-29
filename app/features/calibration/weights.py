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
from app.features.calibration.agreement import icc2, pearson, spearman
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


FLOOR = 0.05  # owner decision 2026-09-29: no axis may drop below 5%
_STEPS = (0.1, 0.05, 0.02, 0.01, 0.005, 0.002, 0.001)


def _fit_score(engine: dict[str, dict], human: dict[str, float], sessions: list[str],
               weights: dict[str, float]) -> float:
    r = pearson([weighted_overall(engine[s]["axes"], weights) for s in sessions], [human[s] for s in sessions])
    return -math.inf if math.isnan(r) else r


def _on_floor(weights: dict[str, float], floor: float) -> dict[str, float]:
    """Scale a weight set into the feasible region: every weight >= floor, sum 1."""
    total = sum(weights.values())
    return {a: floor + (1 - len(AXES) * floor) * weights[a] / total for a in AXES}


def _search(start: dict[str, float], score, floor: float) -> tuple[dict[str, float], float]:
    """Derivative-free local search on the simplex: move weight from one axis to
    another while it improves the score, with shrinking steps."""
    w, best = dict(start), score(start)
    for step in _STEPS:
        improved = True
        while improved:
            improved = False
            for give in AXES:
                for take in AXES:
                    amount = min(step, w[give] - floor)
                    if give == take or amount <= 1e-12:
                        continue
                    trial = {**w, give: w[give] - amount, take: w[take] + amount}
                    value = score(trial)
                    if value > best + 1e-12:
                        w, best, improved = trial, value, True
    return w, best


def fit_weights(engine: dict[str, dict], human: dict[str, float], floor: float = FLOOR) -> dict[str, float]:
    """Weights (each >= floor, sum 1) whose overall correlates best (Pearson) with
    the human mean level on the given sessions. Several starts: current, equal,
    and one leaning on each axis; the best local optimum wins."""
    sessions = sorted(set(engine) & set(human))

    def score(weights: dict[str, float]) -> float:
        return _fit_score(engine, human, sessions, weights)

    corner = 1 - (len(AXES) - 1) * floor
    starts = [_on_floor(WEIGHTS, floor), _on_floor({a: 1.0 for a in AXES}, floor),
              *({b: (corner if b == a else floor) for b in AXES} for a in AXES)]
    best_w, best = starts[0], -math.inf
    for start in starts:
        w, value = _search(start, score, floor)
        if value > best:
            best_w, best = w, value
    return best_w


def loo_predictions(engine: dict[str, dict], human: dict[str, float],
                    floor: float = FLOOR) -> tuple[dict[str, float], list[dict[str, float]]]:
    """Leave-one-out: each session's overall under weights fitted without it,
    plus the weights of every fold (to show how stable the fit is)."""
    sessions = sorted(set(engine) & set(human))
    predictions, folds = {}, []
    for held_out in sessions:
        rest = [s for s in sessions if s != held_out]
        w = fit_weights({s: engine[s] for s in rest}, {s: human[s] for s in rest}, floor)
        folds.append(w)
        predictions[held_out] = weighted_overall(engine[held_out]["axes"], w)
    return predictions, folds


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
