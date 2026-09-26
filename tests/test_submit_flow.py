import pytest

import app.features.mentor.client as client_mod
import app.features.attempts.scoring_service as scoring_service

pytestmark = pytest.mark.asyncio


class FakeClient:
    _model = "fake"

    async def chat(self, *a, **k):
        return {"text": "", "prompt_tokens": 0, "completion_tokens": 0, "code_loc": 0}

    async def judge(self, system, user, max_tokens=300):
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

    # feedback shape is consistent between explain-back and report: timeline lives only
    # at the top level, never embedded inside feedback.
    assert "timeline" not in body["feedback"]
    assert "timeline" not in rep.json()["feedback"]
    assert len(rep.json()["timeline"]) == 3
    assert rep.json()["timeline"] == body["timeline"]


async def test_explain_back_stores_the_judges_verdicts(client, db_session, auth_headers, monkeypatch):
    from sqlalchemy import select

    from app.models import Event, PromptLog

    class Judging(FakeClient):
        async def judge(self, system, user, max_tokens=300):
            if "rate each message" in system:
                return {"prompts": [{"i": 1, "level": 2, "evidence": "why does n = 0 fail"}]}
            if "explain-back" in system:
                return {"questions": ["Why?"]}
            return {"score": 14, "level": 2, "evidence": "hash map"}

    fake = Judging()
    monkeypatch.setattr(client_mod, "get_mentor_client", lambda: fake)
    monkeypatch.setattr(scoring_service, "get_mentor_client", lambda: fake)
    aid = await _seed_attempt(client, db_session, auth_headers)
    db_session.add(PromptLog(attempt_id=aid, prompt="why does n = 0 fail?", response="Think about range."))
    await db_session.commit()
    await client.post(f"/api/attempts/{aid}/submit", headers=auth_headers)
    eb = await client.post(f"/api/attempts/{aid}/explain-back", headers=auth_headers, json={
        "answers": [{"question": "Why?", "answer": "Because I use a hash map for O(1) lookups."}]})
    assert eb.status_code == 200

    events = (await db_session.execute(select(Event).where(Event.attempt_id == aid, Event.type == "JUDGE"))).scalars()
    judged = {e.payload["kind"]: e.payload for e in events}
    assert judged["explain"]["levels"] == [2] and judged["explain"]["evidence"] == ["hash map"]
    assert judged["prompts"]["levels"] == [2] and judged["prompts"]["model"] == "fake"
    # v1 still scores from the 0-20 explain score.
    assert eb.json()["axes"]["understanding"] > 0


async def test_engine_v2_reports_levels_and_evidence(client, db_session, auth_headers, monkeypatch):
    from app.core.config import Settings

    monkeypatch.setattr(scoring_service, "get_settings", lambda: Settings(scoring_engine="v2"))
    aid = await _seed_attempt(client, db_session, auth_headers)
    await client.post(f"/api/attempts/{aid}/submit", headers=auth_headers)
    eb = await client.post(f"/api/attempts/{aid}/explain-back", headers=auth_headers, json={
        "answers": [{"question": "Why?", "answer": "Because I use a hash map for O(1) lookups."}]})
    body = eb.json()
    assert eb.status_code == 200
    fb = body["feedback"]
    assert fb["engine"] == "v2"
    assert set(fb["levels"]) == {"understanding", "hypothesis", "prompting", "verification", "testing",
                                 "debugging"}
    assert fb["levels"]["prompting"] is None and fb["not_applicable"]["prompting"] == "no_ai_use"
    assert fb["evidence"]["hypothesis"]["reason"] == "verdict_only"  # seeded hypothesis has no level
    rep = (await client.get(f"/api/attempts/{aid}/report", headers=auth_headers)).json()
    assert rep["feedback"]["levels"] == fb["levels"] and rep["overall"] == body["overall"]


async def test_explain_back_twice_returns_409(client, db_session, auth_headers):
    aid = await _seed_attempt(client, db_session, auth_headers)
    await client.post(f"/api/attempts/{aid}/submit", headers=auth_headers)
    answers = {"answers": [{"question": "q", "answer": "a"}]}
    first = await client.post(f"/api/attempts/{aid}/explain-back", headers=auth_headers, json=answers)
    assert first.status_code == 200
    second = await client.post(f"/api/attempts/{aid}/explain-back", headers=auth_headers, json=answers)
    assert second.status_code == 409


async def test_report_marks_axes_without_opportunity_not_applicable(client, db_session, auth_headers):
    aid = await _seed_attempt(client, db_session, auth_headers)
    await client.post(f"/api/attempts/{aid}/submit", headers=auth_headers)
    eb = await client.post(
        f"/api/attempts/{aid}/explain-back", headers=auth_headers,
        json={"answers": [{"question": "q", "answer": "Because I use a hash map for O(1) lookups."}]},
    )
    body = eb.json()
    assert body["axes"]["prompting"] is None
    assert body["axes"]["verification"] is None
    assert body["axes"]["debugging"] is None
    assert body["feedback"]["not_applicable"] == {
        "prompting": "no_ai_use", "verification": "no_ai_code", "debugging": "no_failure",
    }
    rep = (await client.get(f"/api/attempts/{aid}/report", headers=auth_headers)).json()
    assert rep["axes"]["prompting"] is None
    assert rep["feedback"]["not_applicable"] == body["feedback"]["not_applicable"]
