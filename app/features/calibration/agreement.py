"""Agreement statistics for the golden set (pure Python, no numpy).

- icc2: intraclass correlation ICC(2,1) and ICC(2,k) (two-way random effects,
  absolute agreement; Shrout & Fleiss 1979) for a subjects x raters matrix.
- quadratic_kappa / mean_pairwise_kappa: weighted Cohen's kappa for the 0-3
  axis levels, averaged over rater pairs; "not applicable" (None) is handled
  separately so it neither inflates nor deflates agreement on the levels.
- spearman: rank correlation (average ranks for ties), engine vs humans.
"""
import itertools
import math


def icc2(x: list[list[float]]) -> tuple[float, float]:
    """(ICC(2,1), ICC(2,k)) for n subjects (rows) rated by k raters (columns)."""
    n, k = len(x), len(x[0])
    grand = sum(map(sum, x)) / (n * k)
    row_means = [sum(row) / k for row in x]
    col_means = [sum(x[i][j] for i in range(n)) / n for j in range(k)]
    ss_rows = k * sum((m - grand) ** 2 for m in row_means)
    ss_cols = n * sum((m - grand) ** 2 for m in col_means)
    ss_total = sum((v - grand) ** 2 for row in x for v in row)
    ms_rows = ss_rows / (n - 1)
    ms_cols = ss_cols / (k - 1)
    ms_error = (ss_total - ss_rows - ss_cols) / ((n - 1) * (k - 1))
    single_den = ms_rows + (k - 1) * ms_error + k * (ms_cols - ms_error) / n
    average_den = ms_rows + (ms_cols - ms_error) / n
    if single_den == 0 or average_den == 0:
        return math.nan, math.nan
    return (ms_rows - ms_error) / single_den, (ms_rows - ms_error) / average_den


def quadratic_kappa(a: list[int], b: list[int], categories: int = 4) -> float:
    """Quadratic-weighted Cohen's kappa between two raters on levels 0..categories-1."""
    n = len(a)
    observed = [[0.0] * categories for _ in range(categories)]
    for x, y in zip(a, b):
        observed[x][y] += 1
    hist_a = [sum(row) for row in observed]
    hist_b = [sum(observed[i][j] for i in range(categories)) for j in range(categories)]
    weight = [[(i - j) ** 2 / (categories - 1) ** 2 for j in range(categories)] for i in range(categories)]
    num = sum(weight[i][j] * observed[i][j] for i in range(categories) for j in range(categories))
    den = sum(weight[i][j] * hist_a[i] * hist_b[j] / n for i in range(categories) for j in range(categories))
    if den == 0:
        # Both raters used one identical level throughout: perfect but uninformative.
        return 1.0 if list(a) == list(b) else 0.0
    return 1 - num / den


def mean_pairwise_kappa(ratings: dict[str, list[int | None]], categories: int = 4) -> dict:
    """Mean kappa over rater pairs on the items both scored, plus how often a
    pair agrees on "not applicable" among items where either said so."""
    kappas, na_hits, na_total = [], 0, 0
    for r1, r2 in itertools.combinations(sorted(ratings), 2):
        both = [(x, y) for x, y in zip(ratings[r1], ratings[r2]) if x is not None and y is not None]
        if len(both) >= 2:
            kappas.append(quadratic_kappa([x for x, _ in both], [y for _, y in both], categories))
        for x, y in zip(ratings[r1], ratings[r2]):
            if x is None or y is None:
                na_total += 1
                na_hits += x is None and y is None
    return {
        "kappa": sum(kappas) / len(kappas) if kappas else math.nan,
        "pairs": len(kappas),
        "na_agreement": na_hits / na_total if na_total else None,
    }


def _ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for t in range(i, j + 1):
            ranks[order[t]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def spearman(x: list[float], y: list[float]) -> float:
    rx, ry = _ranks(x), _ranks(y)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    sx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    sy = math.sqrt(sum((b - my) ** 2 for b in ry))
    return cov / (sx * sy) if sx and sy else math.nan
