"""Analytic Hierarchy Process (Saaty) for the six scoring axes.

Each expert compares every pair of axes on Saaty's 1-9 scale; the weights are
the principal eigenvector of the resulting reciprocal matrix, and the
consistency ratio (CR) flags self-contradicting answers (CR >= 0.1 means the
expert should revisit the pairs `worst_pairs` points at). Group weights come
from the element-wise geometric mean of the individual matrices (AIJ).
"""
import math

AXES = ("understanding", "hypothesis", "prompting", "verification", "testing", "debugging")
PAIRS = tuple((AXES[i], AXES[j]) for i in range(len(AXES)) for j in range(i + 1, len(AXES)))

# Saaty's random consistency index by matrix size.
RANDOM_INDEX = {1: 0.0, 2: 0.0, 3: 0.58, 4: 0.90, 5: 1.12, 6: 1.24, 7: 1.32, 8: 1.41, 9: 1.45, 10: 1.49}
CR_THRESHOLD = 0.1
_EPS = 1e-9

Matrix = list[list[float]]


def matrix(answers: dict[tuple[str, str], float]) -> Matrix:
    """Reciprocal comparison matrix from `answers[(a, b)]` = how much more
    important a is than b: 1..9 when a wins, 1/9..1 when b wins."""
    index = {axis: i for i, axis in enumerate(AXES)}
    m = [[1.0] * len(AXES) for _ in AXES]
    for a, b in PAIRS:
        if (a, b) not in answers:
            raise ValueError(f"missing comparison {a} vs {b}")
        value = float(answers[(a, b)])
        if not (1 / 9 - _EPS <= value <= 9 + _EPS):
            raise ValueError(f"{a} vs {b}: {value} is outside Saaty's 1/9..9 scale")
        m[index[a]][index[b]] = value
        m[index[b]][index[a]] = 1 / value
    return m


def _multiply(m: Matrix, w: list[float]) -> list[float]:
    return [sum(row[j] * w[j] for j in range(len(w))) for row in m]


def priorities(m: Matrix, iterations: int = 1000) -> list[float]:
    """Principal eigenvector (power iteration), normalised to sum to 1."""
    n = len(m)
    w = [1 / n] * n
    for _ in range(iterations):
        v = _multiply(m, w)
        total = sum(v)
        v = [x / total for x in v]
        if max(abs(a - b) for a, b in zip(v, w)) < 1e-12:
            return v
        w = v
    return w


def consistency_ratio(m: Matrix) -> float:
    n = len(m)
    w = priorities(m)
    lambda_max = sum(mw / wi for mw, wi in zip(_multiply(m, w), w)) / n
    return ((lambda_max - n) / (n - 1)) / RANDOM_INDEX[n]


def aggregate(matrices: list[Matrix]) -> Matrix:
    """Group matrix: element-wise geometric mean of the experts' matrices."""
    n = len(matrices[0])
    return [[math.prod(m[i][j] for m in matrices) ** (1 / len(matrices)) for j in range(n)] for i in range(n)]


def worst_pairs(m: Matrix, k: int = 3) -> list[tuple[str, str]]:
    """Pairs whose answer strays furthest from what the derived weights imply."""
    w = priorities(m)
    deviation = {
        (AXES[i], AXES[j]): abs(math.log(m[i][j] * w[j] / w[i]))
        for i in range(len(AXES)) for j in range(i + 1, len(AXES))
    }
    return sorted(deviation, key=deviation.get, reverse=True)[:k]
