from datetime import date, timedelta


def test_streak_zero_when_no_attempts():
    from app.features.daily.streak import compute_streak

    assert compute_streak(set(), date(2026, 7, 4)) == 0


def test_streak_counts_consecutive_days_ending_today():
    from app.features.daily.streak import compute_streak

    today = date(2026, 7, 4)
    dates = {today, today - timedelta(days=1), today - timedelta(days=2)}
    assert compute_streak(dates, today) == 3


def test_streak_survives_if_today_not_played_yet_but_yesterday_was():
    from app.features.daily.streak import compute_streak

    today = date(2026, 7, 4)
    dates = {today - timedelta(days=1), today - timedelta(days=2)}
    assert compute_streak(dates, today) == 2


def test_streak_resets_after_a_full_gap_day():
    from app.features.daily.streak import compute_streak

    today = date(2026, 7, 4)
    # Played 3 and 4 days ago, but skipped yesterday and today.
    dates = {today - timedelta(days=3), today - timedelta(days=4)}
    assert compute_streak(dates, today) == 0


def test_streak_breaks_at_first_gap_counting_backward():
    from app.features.daily.streak import compute_streak

    today = date(2026, 7, 4)
    # Today and yesterday played, then a gap, then two older days - streak
    # must stop at the gap and not count the older run.
    dates = {today, today - timedelta(days=1), today - timedelta(days=3), today - timedelta(days=4)}
    assert compute_streak(dates, today) == 2
