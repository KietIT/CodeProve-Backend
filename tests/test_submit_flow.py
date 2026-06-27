import pytest

import app.features.mentor.client as client_mod
import app.features.attempts.scoring_service as scoring_service

pytestmark = pytest.mark.asyncio


class FakeClient:
    _model = "fake"

    async def chat(self, *a, **k):
        return {"text": "", "prompt_tokens": 0, "completion_tokens": 0, "code_loc": 0}

    async def judge(self, system, user):
        if "explain-back questions" in system or "questions" in system:
            return {"questions": ["Why is your approach O(n)?"]}
        return {"score": 16, "reason": "solid"}


@pytest.fixture(autouse=True)
def _patch(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(client_mod, "get_mentor_client", lambda: fake)
    monkeypatch.setattr(scoring_service, "get_mentor_client", lambda: fake)


async def _seed_attempt(client, db_session, auth_headers):
    from app.models import Exercise
    ex = Exercise(
        code="CP-001", title="t", difficulty="Easy", category="Algorithms", level="fresher",
        language="python", acceptance=1, summary="sum", starter_code="x", hint="h",
        domain_keywords=["hash map"],
    )
    db_session.add(ex)
    await db_session.commit()
    aid = (
        await client.post("/api/attempts", json={"exercise_code": "CP-001"}, headers=auth_headers)
    ).json()["attempt_id"]
    await client.post(
        f"/api/attempts/{aid}/events",
        headers=auth_headers,
        json={"events": [
            {"type": "HYPOTHESIS", "ts": 1000, "payload": {"proposedBy": "user", "correct": True}},
        ]},
    )
    return aid


async def test_submit_then_explain_back_produces_report(client, db_session, auth_headers):
    aid = await _seed_attempt(client, db_session, auth_headers)

    sub = await client.post(f"/api/attempts/{aid}/submit", headers=auth_headers)
    assert sub.status_code == 200
    questions = sub.json()["questions"]
    assert len(questions) >= 1

    eb = await client.post(
        f"/api/attempts/{aid}/explain-back",
        headers=auth_headers,
        json={"answers": [{"question": questions[0], "answer": "Because I use a hash map for O(1) lookups."}]},
    )
    assert eb.status_code == 200
    body = eb.json()
    assert 0 <= body["overall"] <= 100
    assert "understanding" in body["axes"]
    assert body["integrity_status"] in ("green", "yellow", "red")

    rep = await client.get(f"/api/attempts/{aid}/report", headers=auth_headers)
    assert rep.json()["overall"] == body["overall"]
