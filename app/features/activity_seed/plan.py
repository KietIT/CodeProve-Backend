"""Pure planning of seeded practice activity: which exercise, when, and with what scores.

No database access here, so the plan is deterministic for a given RNG and easy to test.
Times are planned in Vietnam local time (when the learners actually study) and returned in UTC.
"""
import random
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.features.scoring.engine import NA_REASONS, WEIGHTS, weighted_overall

LOCAL_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
DAY_START = time(7, 0)
DAY_END = time(23, 30)
MIN_PER_DAY, MAX_PER_DAY = 3, 5

# Relative chance that a study session starts in each local hour: lunch break and evening peaks.
SESSION_START_WEIGHTS: dict[int, float] = {
    7: 1, 8: 2, 9: 3, 10: 3, 11: 2, 12: 3, 13: 3, 14: 3, 15: 3, 16: 3,
    17: 2, 18: 2, 19: 4, 20: 6, 21: 7, 22: 4,
}
# Minutes a learner spends on one exercise, by difficulty.
DURATION_MINUTES: dict[str, tuple[int, int]] = {"Easy": (8, 20), "Medium": (15, 35), "Hard": (25, 50)}
BREAK_MINUTES = (2, 12)  # between two exercises of one session
DIFFICULTY_OFFSET: dict[str, float] = {"Easy": 7.0, "Medium": 0.0, "Hard": -9.0}
LEVEL_ORDER = ("fresher", "junior", "senior")
PLACEMENT_TRIES = 80


@dataclass(frozen=True)
class ExerciseInfo:
    id: int
    level: str
    difficulty: str
    kind: str


@dataclass(frozen=True)
class PlannedAttempt:
    exercise_id: int
    started_at: datetime  # UTC
    submitted_at: datetime  # UTC
    axes: dict[str, float | None]  # 0-20 per axis, None = not applicable
    overall: float
    explanation: float
    integrity: str  # green | yellow


@dataclass
class Learner:
    """Per-learner traits drawn once, so one person's scores stay coherent across days."""
    ability: float  # expected overall on a Medium exercise on day 0
    growth: float  # points gained per active day
    uses_ai: float  # chance an attempt has prompting/verification evidence


Interval = tuple[datetime, datetime]


def draw_learner(rng: random.Random) -> Learner:
    return Learner(ability=rng.uniform(52, 76), growth=rng.uniform(0.25, 0.7), uses_ai=rng.uniform(0.6, 0.9))


def _level_weights(progress: float) -> dict[str, float]:
    # Early days are mostly fresher exercises; later days mix in junior and senior ones.
    return {"fresher": max(0.15, 1.0 - 0.8 * progress), "junior": 0.3 + 0.5 * progress, "senior": 0.05 + 0.5 * progress}


def pick_exercise(rng: random.Random, exercises: list[ExerciseInfo], done: dict[int, int],
                  progress: float, today: set[int]) -> ExerciseInfo:
    """An exercise the learner has done least (never the same one twice a day if avoidable),
    weighted towards the level that fits how far along they are."""
    fresh = [ex for ex in exercises if ex.id not in today] or exercises
    least = min(done.get(ex.id, 0) for ex in fresh)
    candidates = [ex for ex in fresh if done.get(ex.id, 0) == least]
    weights = _level_weights(progress)
    return rng.choices(candidates, weights=[weights.get(ex.level, 0.3) for ex in candidates])[0]


def _overlaps(a: Interval, others: list[Interval]) -> bool:
    return any(a[0] < b[1] and b[0] < a[1] for b in others)


def _local(day: date, at: time) -> datetime:
    return datetime.combine(day, at, tzinfo=LOCAL_TZ)


def place_day(rng: random.Random, durations: list[int], window: Interval, busy: list[Interval]) -> list[Interval] | None:
    """Start/end times for these attempts in one or two sessions inside `window`, clear of `busy`."""
    lo, hi = window
    hours = [h for h in SESSION_START_WEIGHTS if lo.astimezone(LOCAL_TZ).hour <= h <= hi.astimezone(LOCAL_TZ).hour]
    if not hours:
        return None
    day = lo.astimezone(LOCAL_TZ).date()
    for _ in range(PLACEMENT_TRIES):
        sessions = 1 if len(durations) <= 3 or rng.random() < 0.4 else 2
        cut = rng.randint(1, len(durations) - 1) if sessions == 2 else len(durations)
        groups = [durations[:cut], durations[cut:]] if sessions == 2 else [durations]
        placed: list[Interval] = []
        for group in groups:
            hour = rng.choices(hours, weights=[SESSION_START_WEIGHTS[h] for h in hours])[0]
            cursor = _local(day, time(hour, rng.randint(0, 59), rng.randint(0, 59)))
            for minutes in group:
                end = cursor + timedelta(minutes=minutes, seconds=rng.randint(0, 59))
                placed.append((cursor, end))
                cursor = end + timedelta(minutes=rng.randint(*BREAK_MINUTES), seconds=rng.randint(0, 59))
        inside = all(lo <= s and e <= hi for s, e in placed)
        clear = all(not _overlaps(iv, busy) and not _overlaps(iv, placed[:i]) for i, iv in enumerate(placed))
        if inside and clear:
            return placed  # same order as `durations`
    return None


def draw_scores(rng: random.Random, learner: Learner, ex: ExerciseInfo, active_day: int) -> tuple[dict[str, float | None], float]:
    """Axis scores (0-20) around the learner's current level; returns (axes, overall)."""
    target = min(92.0, learner.ability + learner.growth * active_day) + DIFFICULTY_OFFSET.get(ex.difficulty, 0.0)
    target += rng.gauss(0, 6)
    axes: dict[str, float | None] = {}
    for axis in WEIGHTS:
        axes[axis] = round(max(2.0, min(20.0, target / 5 + rng.gauss(0, 1.6))), 2)
    if rng.random() > learner.uses_ai:
        axes["prompting"] = None
        axes["verification"] = None
    elif rng.random() < 0.2:
        axes["verification"] = None
    if ex.kind != "debug" and rng.random() < 0.55:
        axes["debugging"] = None
    return axes, weighted_overall(axes, WEIGHTS)


def not_applicable(axes: dict[str, float | None]) -> dict[str, str]:
    return {a: NA_REASONS[a] for a, v in axes.items() if v is None and a in NA_REASONS}


def plan_learner(rng: random.Random, signup_at: datetime, now: datetime, exercises: list[ExerciseInfo],
                 done: dict[int, int] | None = None, busy: list[Interval] | None = None) -> list[PlannedAttempt]:
    """3-5 attempts on every day from signup to now (fewer only where the day's window is too short)."""
    if not exercises:
        return []
    done = dict(done or {})
    busy = list(busy or [])
    learner = draw_learner(rng)
    first_day = signup_at.astimezone(LOCAL_TZ).date()
    last_day = now.astimezone(LOCAL_TZ).date()
    total_days = max(1, (last_day - first_day).days)
    out: list[PlannedAttempt] = []
    day = first_day
    while day <= last_day:
        index = (day - first_day).days
        lo = max(_local(day, DAY_START), signup_at + timedelta(minutes=10))
        hi = min(_local(day, DAY_END), now - timedelta(minutes=5))
        day += timedelta(days=1)
        if hi <= lo:
            continue
        picked: list[ExerciseInfo] = []
        for _ in range(rng.randint(MIN_PER_DAY, MAX_PER_DAY)):
            picked.append(pick_exercise(rng, exercises, done, index / total_days, {e.id for e in picked}))
        durations = [rng.randint(*DURATION_MINUTES.get(ex.difficulty, (12, 30))) for ex in picked]
        slots = None
        while picked and slots is None:
            slots = place_day(rng, durations, (lo, hi), busy)
            if slots is None:
                picked, durations = picked[:-1], durations[:-1]
        for ex, (start, end) in zip(picked, slots or []):
            done[ex.id] = done.get(ex.id, 0) + 1
            axes, overall = draw_scores(rng, learner, ex, index)
            out.append(PlannedAttempt(
                exercise_id=ex.id,
                started_at=start.astimezone(timezone.utc), submitted_at=end.astimezone(timezone.utc),
                axes=axes, overall=overall, explanation=axes["understanding"] or 0.0,
                integrity="yellow" if rng.random() < 0.07 else "green",
            ))
            busy.append((start, end))
    return out
