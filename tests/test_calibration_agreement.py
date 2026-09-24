import pytest

from app.features.calibration.agreement import icc2, mean_pairwise_kappa, quadratic_kappa, spearman

# Shrout & Fleiss (1979), Table 2: 6 subjects rated by 4 judges.
SHROUT_FLEISS = [
    [9, 2, 5, 8],
    [6, 1, 3, 2],
    [8, 4, 6, 8],
    [7, 1, 2, 6],
    [10, 5, 6, 9],
    [6, 2, 4, 7],
]


def test_icc2_matches_the_published_example():
    single, average = icc2(SHROUT_FLEISS)
    assert single == pytest.approx(0.29, abs=0.005)
    assert average == pytest.approx(0.62, abs=0.005)


def test_icc2_is_one_when_raters_agree_exactly():
    single, average = icc2([[0, 0, 0], [1, 1, 1], [3, 3, 3], [2, 2, 2]])
    assert single == pytest.approx(1.0)
    assert average == pytest.approx(1.0)


def test_quadratic_kappa_bounds():
    assert quadratic_kappa([0, 1, 2, 3], [0, 1, 2, 3]) == pytest.approx(1.0)
    assert quadratic_kappa([0, 0, 3, 3], [3, 3, 0, 0]) == pytest.approx(-1.0)


def test_mean_pairwise_kappa_skips_not_applicable():
    # None = "not applicable": a pair is compared only where both raters scored.
    ratings = {
        "a": [0, 1, 2, 3, None],
        "b": [0, 1, 2, 3, 2],
        "c": [0, 1, 2, 3, None],
    }
    result = mean_pairwise_kappa(ratings)
    assert result["kappa"] == pytest.approx(1.0)
    assert result["pairs"] == 3
    assert result["na_agreement"] == pytest.approx(1 / 3)   # only a/c agree that item 5 is N/A


def test_spearman_with_and_without_ties():
    assert spearman([1, 2, 3, 4], [1, 3, 2, 4]) == pytest.approx(0.8)
    assert spearman([1, 1, 2, 3], [1, 1, 2, 3]) == pytest.approx(1.0)
