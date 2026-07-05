import pytest
from datetime import timedelta

pytestmark = pytest.mark.asyncio


class FakeJudgeClient:
    _model = "fake"

    async def judge(self, system, user, max_tokens=300):
        return {
            "buggy_code": "def f():\n    return 1",
            "buggy_line": 2,
            "bug_category": "off-by-one",
            "hint_1": "h1",
            "hint_2": "h2",
            "explanation": "e",
        }


@pytest.fixture(autouse=True)
def _patch_mentor_client(monkeypatch):
    import app.features.daily.content as content_mod

    monkeypatch.setattr(content_mod, "get_mentor_client", lambda: FakeJudgeClient())


async def test_claim_streak_creates_attempts_for_known_dates(client, db_session, auth_headers):
    # claim_streak resolves "today" itself via today_vn() (for the final
    # streak read) and the earlier /attempt calls in other tests do the same -
    # anchor every date here on today_vn() too, not a hardcoded literal.
    from app.features.daily.service import get_or_create_challenge, today_vn

    today = today_vn()
    yesterday = today - timedelta(days=1)
    await get_or_create_challenge(db_session, today)
    await get_or_create_challenge(db_session, yesterday)

    r = await client.post(
        "/api/daily/claim-streak",
        json={
            "history": [
                {"date": today.isoformat(), "selected_line": 2, "hints_used": 0, "time_taken_seconds": 30},
                {"date": yesterday.isoformat(), "selected_line": 1, "hints_used": 2, "time_taken_seconds": 100},
            ]
        },
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["streak"] == 2


async def test_claim_streak_skips_dates_without_a_challenge(client, auth_headers):
    r = await client.post(
        "/api/daily/claim-streak",
        json={"history": [{"date": "2020-01-01", "selected_line": 1, "hints_used": 0, "time_taken_seconds": 5}]},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["streak"] == 0


async def test_claim_streak_never_overwrites_an_existing_real_attempt(client, db_session, auth_headers):
    from app.features.daily.service import get_or_create_challenge, today_vn

    today = today_vn()
    challenge = await get_or_create_challenge(db_session, today)

    real = await client.post(
        "/api/daily/attempt",
        json={"selected_line": challenge.buggy_line, "hints_used": 0, "time_taken_seconds": 5},
        headers=auth_headers,
    )
    assert real.status_code == 200

    # A claim with a *wrong* selected_line for the same day must not clobber
    # the real green result already recorded.
    claim = await client.post(
        "/api/daily/claim-streak",
        json={"history": [{"date": today.isoformat(), "selected_line": 999, "hints_used": 2, "time_taken_seconds": 200}]},
        headers=auth_headers,
    )
    assert claim.status_code == 200

    today_state = await client.get("/api/daily/today", headers=auth_headers)
    assert today_state.json()["result"]["tier"] == "green"


async def test_claim_streak_requires_auth(client):
    r = await client.post("/api/daily/claim-streak", json={"history": []})
    assert r.status_code == 401


async def test_claim_streak_rejects_more_than_60_history_items(client, auth_headers):
    history = [
        {"date": f"2020-01-{(i % 28) + 1:02d}", "selected_line": 1, "hints_used": 0, "time_taken_seconds": 5}
        for i in range(61)
    ]
    r = await client.post(
        "/api/daily/claim-streak",
        json={"history": history},
        headers=auth_headers,
    )
    assert r.status_code == 422
