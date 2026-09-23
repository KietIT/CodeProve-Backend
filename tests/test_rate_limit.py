import pytest
from fastapi import HTTPException

from app.core import rate_limit


@pytest.fixture
def clock(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(rate_limit.time, "monotonic", lambda: now[0])
    return now


def test_blocks_after_max_calls_and_recovers_after_window(clock):
    assert rate_limit.hit("u", 2, 60) == 0
    assert rate_limit.hit("u", 2, 60) == 0
    assert rate_limit.hit("u", 2, 60) == pytest.approx(60)
    clock[0] += 60
    assert rate_limit.hit("u", 2, 60) == 0


def test_retry_after_is_time_until_oldest_call_expires(clock):
    rate_limit.hit("u", 1, 60)
    clock[0] += 45.5
    with pytest.raises(HTTPException) as exc:
        rate_limit.enforce("u", 1, 60)
    assert exc.value.status_code == 429
    assert exc.value.headers["Retry-After"] == "15"


def test_idle_keys_are_swept(clock):
    for i in range(100):
        rate_limit.hit(f"user-{i}", 5, 60)
    clock[0] += 61
    rate_limit.hit("active", 5, 60)
    assert set(rate_limit._hits) == {"active"}
