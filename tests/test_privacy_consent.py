"""P3.7: consent before the AI features, and the AI-personalisation switch."""
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

import app.features.mentor.client as client_mod
import app.features.mentor.service as service_mod
import app.features.privacy.service as privacy_service
from app.core.security import create_access_token, hash_password
from app.features.mentor.prompts import HINT_STYLE
from app.models import Attempt, Exercise, FluencyReport, LearnerSkill, User

SIGNUP = {"full_name": "Jane Doe", "email": "jane@test.io", "password": "password123"}


class Recording:
    _model = "fake"

    def __init__(self):
        self.calls: list[dict] = []

    async def chat(self, user_message, history, inject_error, context="", extra_instruction=""):
        self.calls.append({"context": context, "instruction": extra_instruction})
        return {"text": "a hint", "prompt_tokens": 1, "completion_tokens": 1, "code_loc": 0}

    async def judge(self, system, user, max_tokens=300):
        return {"correct": True, "note": "ok", "level": 2, "evidence": "e"}


@pytest.fixture
def ciel(monkeypatch):
    fake = Recording()
    monkeypatch.setattr(client_mod, "get_mentor_client", lambda: fake)
    monkeypatch.setattr(service_mod, "get_mentor_client", lambda: fake)
    return fake


@pytest.mark.parametrize("extra", [{}, {"accept_privacy": False}])
async def test_signup_needs_the_policy_accepted(client, extra):
    assert (await client.post("/api/auth/signup", json={**SIGNUP, **extra})).status_code == 422


async def test_signup_records_consent(client):
    r = await client.post("/api/auth/signup", json={**SIGNUP, "accept_privacy": True})
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert (await client.get("/api/me/privacy", headers=headers)).json() == {
        "consented": True, "version": "2026-10-2", "current_version": "2026-10-2", "ai_personalization": True}


async def _google_style_user(db_session) -> dict:
    """An account made without the signup form (Google, or created before P3.7): no consent yet."""
    user = User(full_name="Google User", email="g@test.io", password_hash=hash_password("x" * 12))
    db_session.add(user)
    await db_session.commit()
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


async def _exercise(db_session, level="fresher"):
    db_session.add(Exercise(code="CP-001", title="t", difficulty="Easy", category="c", level=level,
                            language="python", summary="s", starter_code="x", hint="h", domain_keywords=[],
                            skills=["hash-map"]))
    await db_session.commit()


async def test_ai_features_wait_for_consent_the_rest_works(client, db_session, ciel):
    headers = await _google_style_user(db_session)
    await _exercise(db_session)
    aid = (await client.post("/api/attempts", json={"exercise_code": "CP-001"}, headers=headers)).json()["attempt_id"]
    base = f"/api/attempts/{aid}"
    for method, url, body in (("post", f"{base}/mentor", {"message": "hint?"}),
                              ("post", f"{base}/hypothesis", {"text": "use a dict"}),
                              ("post", f"{base}/submit", None),
                              ("post", f"{base}/explain-back", {"answers": []})):
        r = await getattr(client, method)(url, json=body, headers=headers)
        assert r.status_code == 403 and r.json()["detail"]["code"] == "privacy_consent_required", url
    assert ciel.calls == []
    for url in (base, "/api/dashboard", "/api/learner/me", "/api/exercises"):
        assert (await client.get(url, headers=headers)).status_code == 200, url


async def test_consent_must_be_for_the_current_version(client, db_session, ciel):
    headers = await _google_style_user(db_session)
    draft = await client.post("/api/me/privacy/consent", json={"version": "2026-10"}, headers=headers)  # the draft
    assert draft.status_code == 409 and draft.json()["detail"]["current_version"] == "2026-10-2"
    ok = await client.post("/api/me/privacy/consent", json={"version": "2026-10-2"}, headers=headers)
    assert ok.status_code == 200 and ok.json()["consented"] is True
    await _exercise(db_session)
    aid = (await client.post("/api/attempts", json={"exercise_code": "CP-001"}, headers=headers)).json()["attempt_id"]
    assert (await client.post(f"/api/attempts/{aid}/mentor", json={"message": "hint?"}, headers=headers)).status_code == 200


async def test_a_new_policy_version_asks_again(client, db_session, auth_headers, ciel, monkeypatch):
    await _exercise(db_session)
    aid = (await client.post("/api/attempts", json={"exercise_code": "CP-001"}, headers=auth_headers)).json()["attempt_id"]
    monkeypatch.setattr(privacy_service, "POLICY_VERSION", "2027-01")
    r = await client.post(f"/api/attempts/{aid}/mentor", json={"message": "hint?"}, headers=auth_headers)
    assert r.status_code == 403
    assert (await client.get("/api/me/privacy", headers=auth_headers)).json()["consented"] is False


async def test_turning_personalisation_off_drops_only_the_brief(client, db_session, auth_headers, ciel):
    await _exercise(db_session)
    user = (await db_session.execute(select(User).where(User.email == "testuser@example.com"))).scalar_one()
    ex = (await db_session.execute(select(Exercise))).scalar_one()
    past = Attempt(user_id=user.id, exercise_id=ex.id, status="scored", score=70.0)
    db_session.add(past); await db_session.flush()
    db_session.add_all([FluencyReport(attempt_id=past.id, understanding_score=0, hypothesis_score=0,
                                      explanation_score=0, overall_score=70.0, feedback={}),
                        LearnerSkill(user_id=user.id, skill="hash-map", rating=1080.0, attempts=3)])
    await db_session.commit()

    off = await client.patch("/api/me/privacy", json={"ai_personalization": False}, headers=auth_headers)
    assert off.json()["ai_personalization"] is False
    aid = (await client.post("/api/attempts", json={"exercise_code": "CP-001"}, headers=auth_headers)).json()["attempt_id"]
    await client.post(f"/api/attempts/{aid}/mentor", json={"message": "hint?"}, headers=auth_headers)
    assert "LEARNER PROFILE" not in ciel.calls[0]["context"]
    assert HINT_STYLE["fresher"] in ciel.calls[0]["instruction"]  # the level's hint style stays

    await client.patch("/api/me/privacy", json={"ai_personalization": True}, headers=auth_headers)
    await client.post(f"/api/attempts/{aid}/mentor", json={"message": "and now?"}, headers=auth_headers)
    assert "LEARNER PROFILE" in ciel.calls[1]["context"]


async def test_accepting_the_draft_is_not_consent_to_the_approved_policy(client, db_session, ciel):
    user = User(full_name="Early User", email="early@test.io", password_hash=hash_password("x" * 12),
                privacy_version="2026-10",  # accepted the draft shown before 2026-10-01
                privacy_consent_at=datetime(2026, 9, 30, tzinfo=timezone.utc))
    db_session.add(user)
    await db_session.commit()
    headers = {"Authorization": f"Bearer {create_access_token(str(user.id))}"}
    state = (await client.get("/api/me/privacy", headers=headers)).json()
    assert state["consented"] is False and state["version"] == "2026-10" and state["current_version"] == "2026-10-2"
