"""P3.3: Elo per skill (pure functions)."""
import pytest

from app.features.learner import elo


def test_expected_is_half_at_equal_ratings_and_rises_with_the_gap():
    assert elo.expected(1000, 1000) == pytest.approx(0.5)
    assert elo.expected(1400, 1000) == pytest.approx(10 / 11)
    assert elo.expected(1000, 1400) == pytest.approx(1 / 11)


@pytest.mark.parametrize("overall,s", [(85, 0.85), (-3, 0.0), (120, 1.0), (None, 0.0)])
def test_outcome_is_overall_over_100_clamped(overall, s):
    assert elo.outcome(overall) == pytest.approx(s)


def test_difficulty_defaults_to_the_level_until_rated():
    assert elo.difficulty(None, "fresher") == 900
    assert elo.difficulty(None, "senior") == 1300
    assert elo.difficulty(None, "unknown") == elo.START_RATING
    assert elo.difficulty(1042.5, "fresher") == 1042.5


def test_a_result_above_expectation_raises_every_tag_and_lowers_the_difficulty():
    ratings, d = elo.update({"hash-map": 1000.0, "two-pointers": 1000.0}, 1000.0, 90, move_difficulty=True)
    gain = elo.K_STUDENT * (0.9 - 0.5)
    assert ratings == pytest.approx({"hash-map": 1000 + gain, "two-pointers": 1000 + gain})
    assert d == pytest.approx(1000 - elo.K_EXERCISE * 0.4)


def test_a_result_below_expectation_lowers_the_rating_and_raises_the_difficulty():
    ratings, d = elo.update({"graph": 1100.0}, 900.0, 30, move_difficulty=True)
    e = elo.expected(1100, 900)
    assert ratings["graph"] == pytest.approx(1100 + elo.K_STUDENT * (0.3 - e))
    assert d > 900


def test_difficulty_uses_the_mean_rating_over_the_tags():
    _, d = elo.update({"a": 900.0, "b": 1100.0}, 1000.0, 50, move_difficulty=True)
    assert d == pytest.approx(1000.0)  # mean rating 1000 vs D 1000: expected 0.5 = outcome


def test_move_difficulty_false_keeps_it_and_no_tags_change_nothing():
    ratings, d = elo.update({"graph": 1000.0}, 1000.0, 90, move_difficulty=False)
    assert d == 1000.0 and ratings["graph"] > 1000
    assert elo.update({}, 1000.0, 90, move_difficulty=True) == ({}, 1000.0)
