"""In-process sliding-window rate limiter.

Good enough for a single uvicorn worker. With several workers/instances each
keeps its own counters, so move this to Redis if the backend scales out.
"""
import time
from collections import deque

from fastapi import HTTPException, status

_hits: dict[str, deque[float]] = {}


def allow(key: str, max_calls: int, window_seconds: float) -> bool:
    """Record a call for `key`; False if it would exceed `max_calls` per window."""
    now = time.monotonic()
    hits = _hits.setdefault(key, deque())
    while hits and now - hits[0] >= window_seconds:
        hits.popleft()
    if len(hits) >= max_calls:
        return False
    hits.append(now)
    return True


def enforce(key: str, max_calls: int, window_seconds: float) -> None:
    if not allow(key, max_calls, window_seconds):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests, please slow down",
            headers={"Retry-After": str(int(window_seconds))},
        )


def reset() -> None:
    _hits.clear()
