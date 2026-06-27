import pytest

import app.features.mentor.client as client_mod
import app.features.mentor.service as service_mod

pytestmark = pytest.mark.asyncio


class FakeClient:
    _model = "fake"

    async def chat(self, user_message, history, inject_error):
        return {
            "text": "Consider edge cases. ```py\nfor i in range(n):\n    pass\n```",
            "prompt_tokens": 12,
            "completion_tokens": 20,
            "code_loc": 2,
        }

    async def judge(self, system, user):
        return {"correct": True, "note": "hash map approach is right"}


@pytest.fixture(autouse=True)
def _patch(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(client_mod, "get_mentor_client", lambda: fake)
    monkeypatch.setattr(service_mod, "get_mentor_client", lambda: fake)


async def _seed_attempt(client, db_session, auth_headers, trap=True):
    from app.models import Exercise

    ex = Exercise(
        code="CP-001",
        title="t",
        difficulty="Easy",
        category="Algorithms",
        level="fresher",
        language="python",
        acceptance=1,
        summary="sum two",
        starter_code="x",
        hint="h",
        domain_keywords=["hash map", "target"],
        verification_trap=trap,
    )
    db_session.add(ex)
    await db_session.commit()
    r = await client.post(
        "/api/attempts", json={"exercise_code": "CP-001"}, headers=auth_headers
    )
    return r.json()["attempt_id"]


async def _events(db_session, attempt_id):
    from sqlalchemy import select

    from app.models import Event

    return (await db_session.execute(select(Event).where(Event.attempt_id == attempt_id))).scalars().all()


async def test_mentor_injects_error_once(client, db_session, auth_headers):
    aid = await _seed_attempt(client, db_session, auth_headers, trap=True)
    r1 = await client.post(
        f"/api/attempts/{aid}/mentor",
        json={"message": "how do I find the target with a hash map?"},
        headers=auth_headers,
    )
    assert r1.json()["injected_error"] is True
    r2 = await client.post(
        f"/api/attempts/{aid}/mentor",
        json={"message": "another question"},
        headers=auth_headers,
    )
    assert r2.json()["injected_error"] is False  # only once per attempt

    # PROMPT must record matched domain keywords and AI_REPLY must flag the injection.
    events = await _events(db_session, aid)
    prompt_ev = next(e for e in events if e.type == "PROMPT")
    assert set(prompt_ev.payload["keywordsMatched"]) >= {"hash map", "target"}
    ai_ev = next(e for e in events if e.type == "AI_REPLY")
    assert ai_ev.payload["injectedError"] is True


async def test_no_trap_no_injection(client, db_session, auth_headers):
    aid = await _seed_attempt(client, db_session, auth_headers, trap=False)
    r = await client.post(
        f"/api/attempts/{aid}/mentor",
        json={"message": "any hint about a hash map?"},
        headers=auth_headers,
    )
    assert r.json()["injected_error"] is False


async def test_hypothesis_records_event(client, db_session, auth_headers):
    aid = await _seed_attempt(client, db_session, auth_headers)
    r = await client.post(
        f"/api/attempts/{aid}/hypothesis",
        json={"text": "use a hash map"},
        headers=auth_headers,
    )
    assert r.json()["correct"] is True

    events = await _events(db_session, aid)
    hyp = next(e for e in events if e.type == "HYPOTHESIS")
    assert hyp.payload == {"proposedBy": "user", "correct": True}
