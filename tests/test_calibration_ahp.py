import pytest

from app.features.calibration.ahp import (
    AXES,
    PAIRS,
    aggregate,
    consistency_ratio,
    matrix,
    priorities,
    worst_pairs,
)

WEIGHTS = dict(zip(AXES, [0.30, 0.25, 0.15, 0.15, 0.10, 0.05]))


def _consistent_answers():
    return {(a, b): WEIGHTS[a] / WEIGHTS[b] for a, b in PAIRS}


def test_fifteen_pairs_over_six_axes():
    assert len(AXES) == 6
    assert len(PAIRS) == 15


def test_consistent_answers_give_back_the_weights_with_zero_cr():
    m = matrix(_consistent_answers())
    w = priorities(m)
    for axis, expected in WEIGHTS.items():
        assert w[AXES.index(axis)] == pytest.approx(expected, abs=1e-6)
    assert consistency_ratio(m) == pytest.approx(0.0, abs=1e-6)


def test_a_contradiction_raises_cr_and_is_pointed_out():
    answers = {pair: 1.0 for pair in PAIRS}          # everything equally important...
    answers[("understanding", "testing")] = 9.0       # ...except one wildly different judgement
    answers[("testing", "debugging")] = 9.0
    answers[("understanding", "debugging")] = 1 / 9  # contradicts the two above
    m = matrix(answers)
    assert consistency_ratio(m) > 0.1
    assert ("understanding", "debugging") in worst_pairs(m, k=3)


def test_aggregating_identical_judgements_changes_nothing():
    m = matrix(_consistent_answers())
    agg = aggregate([m, m, m])
    for row, agg_row in zip(m, agg):
        assert agg_row == pytest.approx(row)


def test_matrix_rejects_missing_and_out_of_scale_answers():
    answers = _consistent_answers()
    with pytest.raises(ValueError):
        matrix({k: v for k, v in answers.items() if k != PAIRS[0]})
    answers[PAIRS[0]] = 12.0
    with pytest.raises(ValueError):
        matrix(answers)
