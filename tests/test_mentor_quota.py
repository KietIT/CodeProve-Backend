"""P3.6: per-student caps on Ciel messages and hypothesis checks."""
from datetime import datetime, timedelta, timezone

import pytest

import app.features.mentor.client as client_mod
import app.features.mentor.quota as quota_mod
import app.features.mentor.service as service_mod
from app.core.config import Settings
from app.features.mentor.quota import day_start_utc
from app.models import Exercise, PromptLog


class FakeCiel:
    _model = "fake"

    def __init__(self):
        self.calls = 0

    async def chat(self, user_message, history, inject_error, context="", extra_instruction=""):
        self.calls += 1
        return {"text": f"reply {self.calls}", "prompt_tokens": 1, "completion_tokens": 1, "code_loc": 0}

    async def judge(self, system, user, max_tokens=300):
        return {"correct": True, "note": "ok", "level": 2, "evidence": "e"}


@pytest.fixture
def ciel(monkeypatch):
    fake = FakeCiel()
    monkeypatch.setattr(client_mod, "get_mentor_client", lambda: fake)
    monkeypatch.setattr(service_mod, "get_mentor_client", lambda: fake)
    return fake


@pytest.fixture
def limits(monkeypatch):
    def set_limits(**over):
        values = {"ciel_per_attempt": 100, "ciel_per_day": 100, "ciel_per_minute": 100, "hypothesis_per_attempt": 100,
                  **over}
        monkeypatch.setattr(quota_mod, "get_settings", lambda: Settings(**values))
    return set_limits


async def _attempt(client, db_session, auth_headers) -> int:
    from sqlalchemy import select

    if not (await db_session.execute(select(Exercise))).scalar_one_or_none():
        db_session.add(Exercise(code="CP-001", title="t", difficulty="Easy", category="c", level="junior",
                                language="python", summary="s", starter_code="x", hint="h", domain_keywords=[]))
        await db_session.commit()
    return (await client.post("/api/attempts", json={"exercise_code": "CP-001"}, headers=auth_headers)).json()["attempt_id"]


async def _ask(client, aid, headers, message="hint please"):
    return await client.post(f"/api/attempts/{aid}/mentor", json={"message": message}, headers=headers)


async def test_the_attempt_limit_and_the_remaining_count(client, db_session, auth_headers, ciel, limits):
    limits(ciel_per_attempt=3)
    aid = await _attempt(client, db_session, auth_headers)
    lefts = [(await _ask(client, aid, auth_headers)).json()["ciel"]["attempt_left"] for _ in range(3)]
    assert lefts == [2, 1, 0]
    refused = await _ask(client, aid, auth_headers)
    assert refused.status_code == 429
    assert refused.json()["detail"] == {"code": "ciel_attempt_limit",
                                        "message_vi": "Bạn đã dùng hết 3 tin nhắn với Ciel cho lượt làm bài này.",
                                        "message_en": "You have used all 3 Ciel messages for this attempt."}
    assert ciel.calls == 3  # the refused message never reached the LLM
    state = (await client.get(f"/api/attempts/{aid}", headers=auth_headers)).json()
    assert state["ciel"] == {"attempt_left": 0, "day_left": 97}


async def test_the_daily_limit_spans_attempts(client, db_session, auth_headers, ciel, limits):
    limits(ciel_per_day=3)
    first = await _attempt(client, db_session, auth_headers)
    for _ in range(2):
        assert (await _ask(client, first, auth_headers)).status_code == 200
    second = await _attempt(client, db_session, auth_headers)
    assert (await _ask(client, second, auth_headers)).json()["ciel"] == {"attempt_left": 99, "day_left": 0}
    refused = await _ask(client, second, auth_headers)
    assert refused.status_code == 429 and refused.json()["detail"]["code"] == "ciel_daily_limit"


async def test_yesterdays_messages_do_not_count(client, db_session, auth_headers, ciel, limits):
    limits(ciel_per_day=3)
    aid = await _attempt(client, db_session, auth_headers)
    yesterday = day_start_utc() - timedelta(minutes=1)
    db_session.add_all([PromptLog(attempt_id=aid, prompt="old", response="old", created_at=yesterday)
                        for _ in range(3)])
    await db_session.commit()
    reply = await _ask(client, aid, auth_headers)
    assert reply.status_code == 200 and reply.json()["ciel"]["day_left"] == 2


@pytest.mark.parametrize("now,start", [
    (datetime(2026, 10, 1, 16, 30, tzinfo=timezone.utc), datetime(2026, 9, 30, 17, 0, tzinfo=timezone.utc)),
    (datetime(2026, 10, 1, 17, 30, tzinfo=timezone.utc), datetime(2026, 10, 1, 17, 0, tzinfo=timezone.utc)),
])
def test_the_day_starts_at_vietnam_midnight(now, start):
    assert day_start_utc(now) == start


async def test_the_burst_limit(client, db_session, auth_headers, ciel, limits):
    limits(ciel_per_minute=2)
    aid = await _attempt(client, db_session, auth_headers)
    assert [(await _ask(client, aid, auth_headers)).status_code for _ in range(2)] == [200, 200]
    refused = await _ask(client, aid, auth_headers)
    assert refused.status_code == 429 and refused.json()["detail"]["code"] == "rate_limited"
    assert int(refused.headers["Retry-After"]) >= 1


async def test_a_guard_retry_counts_as_one_message(client, db_session, auth_headers, ciel, limits, monkeypatch):
    limits(ciel_per_attempt=5)

    async def always_solves(db, exercise_id, text):
        return True

    monkeypatch.setattr(service_mod.guard, "solves_exercise", always_solves)
    aid = await _attempt(client, db_session, auth_headers)
    reply = await _ask(client, aid, auth_headers)
    assert ciel.calls == 2 and reply.json()["ciel"]["attempt_left"] == 4


async def test_the_hypothesis_limit(client, db_session, auth_headers, ciel, limits):
    limits(hypothesis_per_attempt=2)
    aid = await _attempt(client, db_session, auth_headers)
    url = f"/api/attempts/{aid}/hypothesis"
    for _ in range(2):
        assert (await client.post(url, json={"text": "use a dict"}, headers=auth_headers)).status_code == 200
    refused = await client.post(url, json={"text": "use a dict"}, headers=auth_headers)
    assert refused.status_code == 429 and refused.json()["detail"]["code"] == "hypothesis_limit"


async def test_limits_are_per_student(client, db_session, auth_headers, ciel, limits):
    limits(ciel_per_day=1)
    aid = await _attempt(client, db_session, auth_headers)
    assert (await _ask(client, aid, auth_headers)).status_code == 200
    assert (await _ask(client, aid, auth_headers)).status_code == 429
    r = await client.post("/api/auth/signup", json={"full_name": "Binh Tran", "email": "binh@example.com",
                                                       "password": "password123", "accept_privacy": True})
    assert r.status_code == 200, r.text
    other = {"Authorization": f"Bearer {r.json()['access_token']}"}
    other_aid = await _attempt(client, db_session, other)
    assert (await _ask(client, other_aid, other)).status_code == 200


async def test_overlong_messages_are_rejected_before_the_llm(client, db_session, auth_headers, ciel):
    aid = await _attempt(client, db_session, auth_headers)
    assert (await _ask(client, aid, auth_headers, "x" * 4001)).status_code == 422
    assert (await _ask(client, aid, auth_headers, "")).status_code == 422
    assert ciel.calls == 0
