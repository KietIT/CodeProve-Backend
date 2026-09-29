import math
import random

from app.features.calibration import weights as weights_module
from app.features.calibration.ahp import AXES, PAIRS
from app.features.calibration.analyze import OVERALL_LEVELS, Dump
from app.features.calibration.weights import (
    analyse_weights, bootstrap_delta, candidates, evaluate, fit_weights, human_overall, loo_predictions, overalls,
    render_weights, tier_level,
)
from app.features.scoring.engine import WEIGHTS, weighted_overall

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
    assert evaluate({"S1": 90.0, "S2": 10.0}, {"S1": 2.0, "S2": 0.5})["tier_bias"] == 0.25  # (1 + -0.5) / 2


TRUE = {"understanding": 0.3, "hypothesis": 0.25, "prompting": 0.15, "verification": 0.1, "testing": 0.1,
        "debugging": 0.1}


def _following(weights: dict[str, float], n: int = 40, seed: int = 3) -> tuple[dict, dict]:
    """Humans whose overall level is exactly a weighted mean of the engine axes."""
    rng = random.Random(seed)
    engine = {f"S{i}": {"overall": None, "axes": {a: round(rng.uniform(0, 20), 2) for a in AXES}} for i in range(n)}
    human = {sid: 3 * weighted_overall(e["axes"], weights) / 100 for sid, e in engine.items()}
    return engine, human


def test_fit_recovers_the_weights_humans_follow():
    engine, human = _following(TRUE)
    fitted = fit_weights(engine, human, floor=0.05)
    assert all(abs(fitted[a] - TRUE[a]) <= 0.03 for a in AXES), fitted
    assert math.isclose(sum(fitted.values()), 1.0, abs_tol=1e-9)


def test_fit_respects_the_floor():
    engine, human = _synthetic()  # humans follow testing only: the other axes sit on the floor
    fitted = fit_weights(engine, human, floor=0.05)
    assert min(fitted.values()) >= 0.05 - 1e-9 and math.isclose(sum(fitted.values()), 1.0, abs_tol=1e-9)
    assert fitted["testing"] == max(fitted.values()) and fitted["testing"] >= 0.7


def test_leave_one_out_never_fits_on_the_held_out_session(monkeypatch):
    engine, human = _following(TRUE, n=6)
    seen = []

    def spy(sessions, people, floor):
        seen.append(set(sessions))
        return dict(TRUE)

    monkeypatch.setattr(weights_module, "fit_weights", spy)
    predictions, folds = loo_predictions(engine, human, floor=0.05)
    assert len(seen) == 6 and len(folds) == 6
    for held_out, used in zip(sorted(engine), seen):
        assert held_out not in used and len(used) == 5
    assert predictions == overalls(engine, TRUE)


def _dump_from(engine: dict, human: dict, ahp_answers: dict | None = None) -> Dump:
    """Two raters whose levels average to `human` (rounded to the 0-3 scale)."""
    ratings = {"r1": {}, "r2": {}}
    for sid, level in human.items():
        low = min(3, max(0, math.floor(level)))
        high = min(3, low + (level - low >= 0.5))
        ratings["r1"][sid] = {"overall": OVERALL_LEVELS[low]}
        ratings["r2"][sid] = {"overall": OVERALL_LEVELS[high]}
    return Dump(ahp=ahp_answers or {}, ratings=ratings, engine=engine)


def test_the_rule_keeps_the_current_weights_when_humans_follow_them():
    engine, human = _following(WEIGHTS, n=24)
    result = analyse_weights(_dump_from(engine, human), samples=200)
    assert result["chosen"] == "current"
    assert set(result["sets"]) == {"current", "equal", "regression"}  # no AHP answers: no AHP set


def test_the_rule_picks_the_best_set_when_it_is_clearly_better():
    engine, human = _synthetic(n=40)  # humans follow the testing axis only
    result = analyse_weights(_dump_from(engine, human), samples=200)
    assert result["chosen"] == "regression"
    regression = result["sets"]["regression"]
    assert regression["weights"]["testing"] >= 0.7
    assert regression["delta"][1] > 0  # bootstrap interval vs current excludes 0
    assert len(regression["folds"]) == 40
    assert result["tier_changes"]  # sessions whose tier moves under the chosen set
    report = render_weights(result)
    assert "Bộ được chọn" in report and "regression" in report and "Hạn chế" in report


def test_bootstrap_is_paired_and_deterministic():
    engine, human = _synthetic()
    on_testing = overalls(engine, {a: (0.95 if a == "testing" else 0.01) for a in AXES})
    uniform = overalls(engine, UNIFORM)
    first = bootstrap_delta(on_testing, uniform, human, samples=300, seed=7)
    assert first == bootstrap_delta(on_testing, uniform, human, samples=300, seed=7)
    mean, low, high = first
    assert low <= mean <= high and low > 0  # clearly better: the interval excludes 0
    assert bootstrap_delta(uniform, uniform, human, samples=50) == (0.0, 0.0, 0.0)
