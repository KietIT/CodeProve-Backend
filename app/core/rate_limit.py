"""In-process sliding-window rate limiter.

Good enough for a single uvicorn worker. With several workers/instances each
keeps its own counters, so move this to Redis if the backend scales out.
"""
import math
import time
from collections import deque

from fastapi import HTTPException, status

_hits: dict[str, deque[float]] = {}
_last_sweep = 0.0


def _sweep_idle_keys(now: float, window_seconds: float) -> None:
    """Drop keys with no call inside the window, at most once per window, so
    memory tracks recently active users instead of every user ever seen.
    Assumes all callers share one window length (true today: 60 s)."""
    global _last_sweep
    if now - _last_sweep < window_seconds:
        return
    _last_sweep = now
    for key in [k for k, hits in _hits.items() if not hits or now - hits[-1] >= window_seconds]:
        del _hits[key]


def hit(key: str, max_calls: int, window_seconds: float) -> float:
    """Record a call for `key`. Returns 0 if allowed, otherwise the seconds
    until the oldest call leaves the window and a new one is allowed."""
    now = time.monotonic()
    _sweep_idle_keys(now, window_seconds)
    hits = _hits.setdefault(key, deque())
    while hits and now - hits[0] >= window_seconds:
        hits.popleft()
    if len(hits) >= max_calls:
        return window_seconds - (now - hits[0])
    hits.append(now)
    return 0.0


def enforce(key: str, max_calls: int, window_seconds: float) -> None:
    retry_after = hit(key, max_calls, window_seconds)
    if retry_after > 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests, please slow down",
            headers={"Retry-After": str(max(1, math.ceil(retry_after)))},
        )


def reset() -> None:
    global _last_sweep
    _hits.clear()
    _last_sweep = 0.0
