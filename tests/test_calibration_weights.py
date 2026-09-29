import math
import random

from app.features.calibration.ahp import AXES, PAIRS
from app.features.calibration.analyze import OVERALL_LEVELS, Dump
from app.features.calibration.weights import (
    bootstrap_delta, candidates, evaluate, human_overall, overalls, tier_level,
)
from app.features.scoring.engine import WEIGHTS

UNIFORM = {a: 1 / len(AXES) for a in AXES}


def _answers(weights: dict[str, float]) -> dict:
    return {f"{a}|{b}": weights[a] / weights[b] for a, b in PAIRS}


def _synthetic(n: int = 30, seed: int = 1) -> tuple[dict, dict]:
    """Engine axes with random scores; humans follow the testing axis only."""
    rng = random.Random(seed)
    engine, human = {}, {}
    for i in range(n):
        axes = {a: round(rng.uniform(0, 20), 2) for a in AXES}
        engine[f"S{i}"] = {"overall": None, "axes": axes}
        human[f"S{i}"] = 3 * axes["testing"] / 20
    return engine, human


def test_candidates_include_current_equal_and_the_group_ahp():
    w = {"understanding": 0.3, "hypothesis": 0.25, "prompting": 0.15, "verification": 0.15, "testing": 0.1,
         "debugging": 0.05}
    sets = candidates({"a": _answers(w), "b": _answers(w)})
    assert sets["current"] == dict(WEIGHTS)
    assert sets["equal"] == UNIFORM
    assert all(math.isclose(sets["ahp"][a], w[a], abs_tol=1e-6) for a in AXES)
    assert "ahp_consistent" not in sets  # every member is consistent: same set as "ahp"
    assert set(candidates({})) == {"current", "equal"}


def test_human_overall_is_the_mean_level_over_raters():
    dump = Dump(ratings={
        "r1": {"S1": {"overall": OVERALL_LEVELS[1]}, "S2": {"overall": OVERALL_LEVELS[3]}},
        "r2": {"S1": {"overall": OVERALL_LEVELS[2]}, "S2": {"overall": None}},
    })
    assert human_overall(dump) == {"S1": 1.5, "S2": 3}


def test_tier_levels_follow_the_product_cutoffs():
    assert [tier_level(x) for x in (0, 49.99, 50, 69.99, 70, 84.99, 85, 100)] == [0, 0, 1, 1, 2, 2, 3, 3]


def test_a_set_on_the_axis_humans_follow_agrees_best():
    engine, human = _synthetic()
    on_testing = {a: (0.95 if a == "testing" else 0.01) for a in AXES}
    best = evaluate(overalls(engine, on_testing), human)
    assert best["spearman"] > 0.99 and best["n"] == 30
    assert best["spearman"] > evaluate(overalls(engine, UNIFORM), human)["spearman"]
    assert 0 <= best["tier_exact"] <= 1 and not math.isnan(best["icc"])


def test_bootstrap_is_paired_and_deterministic():
    engine, human = _synthetic()
    on_testing = overalls(engine, {a: (0.95 if a == "testing" else 0.01) for a in AXES})
    uniform = overalls(engine, UNIFORM)
    first = bootstrap_delta(on_testing, uniform, human, samples=300, seed=7)
    assert first == bootstrap_delta(on_testing, uniform, human, samples=300, seed=7)
    mean, low, high = first
    assert low <= mean <= high and low > 0  # clearly better: the interval excludes 0
    assert bootstrap_delta(uniform, uniform, human, samples=50) == (0.0, 0.0, 0.0)
