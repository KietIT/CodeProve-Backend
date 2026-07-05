import pytest

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


class OutageJudgeClient:
    """Simulates an OpenAI outage - the judge call itself raises."""

    _model = "fake"

    async def judge(self, system, user, max_tokens=300):
        raise RuntimeError("OpenAI is down")


@pytest.fixture(autouse=True)
def _patch_mentor_client(monkeypatch):
    import app.features.daily.content as content_mod

    monkeypatch.setattr(content_mod, "get_mentor_client", lambda: FakeJudgeClient())


async def test_today_works_without_auth(client):
    r = await client.get("/api/daily/today")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["already_played"] is False
    assert body["result"] is None
    assert "buggy_line" not in body  # never leak the answer before submit
    assert body["challenge_number"] >= 1


async def test_attempt_works_without_auth_and_does_not_return_streak(client):
    r = await client.post(
        "/api/daily/attempt",
        json={"selected_line": 2, "hints_used": 0, "time_taken_seconds": 10},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["correct"] is True
    assert body["tier"] == "green"
    assert body["streak"] is None


async def test_attempt_with_auth_returns_streak_and_today_reflects_result(client, auth_headers):
    r = await client.post(
        "/api/daily/attempt",
        json={"selected_line": 2, "hints_used": 1, "time_taken_seconds": 90},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["streak"] == 1
    assert r.json()["tier"] == "yellow"

    today = await client.get("/api/daily/today", headers=auth_headers)
    body = today.json()
    assert body["already_played"] is True
    assert body["result"]["tier"] == "yellow"


async def test_attempt_twice_same_day_returns_409(client, auth_headers):
    payload = {"selected_line": 2, "hints_used": 0, "time_taken_seconds": 10}
    r1 = await client.post("/api/daily/attempt", json=payload, headers=auth_headers)
    assert r1.status_code == 200
    r2 = await client.post("/api/daily/attempt", json=payload, headers=auth_headers)
    assert r2.status_code == 409


async def test_regenerate_requires_admin_key(client, monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("ADMIN_API_KEY", "s3cret")
    get_settings.cache_clear()

    forbidden = await client.post("/api/daily/regenerate", headers={"X-Admin-Key": "wrong"})
    assert forbidden.status_code == 403

    ok = await client.post("/api/daily/regenerate", headers={"X-Admin-Key": "s3cret"})
    assert ok.status_code == 200

    get_settings.cache_clear()


async def test_today_returns_503_when_generation_fails(client, monkeypatch):
    import app.features.daily.content as content_mod

    monkeypatch.setattr(content_mod, "get_mentor_client", lambda: OutageJudgeClient())

    r = await client.get("/api/daily/today")
    assert r.status_code == 503, r.text
    assert r.json()["detail"] == "Daily challenge is not ready yet, try again shortly"
