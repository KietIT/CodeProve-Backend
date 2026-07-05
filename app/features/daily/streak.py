from datetime import date, timedelta


def compute_streak(attempt_dates: set[date], today: date) -> int:
    """Current streak = consecutive calendar days with a submitted attempt,
    counted backward from today.

    If today has not been played yet, the streak still counts backward from
    yesterday instead of resetting to 0 - a streak is only broken once a full
    day is skipped (matches Wordle/Duolingo semantics, per spec section 4).
    """
    start = today if today in attempt_dates else today - timedelta(days=1)
    streak = 0
    cursor = start
    while cursor in attempt_dates:
        streak += 1
        cursor -= timedelta(days=1)
    return streak
