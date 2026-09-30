"""Elo per skill (P3.3).

A scored attempt is a "game" between the student and the exercise on each of
the exercise's skills. The result is continuous: overall / 100, which already
carries the integrity multiplier. The student's rating on every tagged skill
moves fast (K_STUDENT); the exercise difficulty moves slowly (K_EXERCISE)
against the student's mean rating over those skills.
"""
START_RATING = 1000.0
LEVEL_DIFFICULTY = {"fresher": 900.0, "junior": 1100.0, "senior": 1300.0}
K_STUDENT = 32.0
K_EXERCISE = 8.0


def expected(rating: float, difficulty: float) -> float:
    return 1 / (1 + 10 ** ((difficulty - rating) / 400))


def outcome(overall: float | None) -> float:
    return min(max((overall or 0.0) / 100, 0.0), 1.0)


def difficulty(stored: float | None, level: str) -> float:
    """The exercise's current difficulty; its level's default until it has been rated."""
    return stored if stored is not None else LEVEL_DIFFICULTY.get(level, START_RATING)


def update(ratings: dict[str, float], current_difficulty: float, overall: float | None,
           move_difficulty: bool) -> tuple[dict[str, float], float]:
    """New ratings for the given skills and the new exercise difficulty."""
    if not ratings:
        return {}, current_difficulty
    s = outcome(overall)
    new = {skill: r + K_STUDENT * (s - expected(r, current_difficulty)) for skill, r in ratings.items()}
    if not move_difficulty:
        return new, current_difficulty
    mean = sum(ratings.values()) / len(ratings)
    return new, current_difficulty - K_EXERCISE * (s - expected(mean, current_difficulty))
