"""P3.5: Ciel gets the learner brief in its context (used silently), never personal data."""
import pytest
from sqlalchemy import select

import app.features.mentor.client as client_mod
import app.features.mentor.service as service_mod
from app.models import Attempt, Exercise, FluencyReport, LearnerSkill, User


class Recording:
    _model = "fake"

    def __init__(self):
        self.contexts: list[str] = []

    async def chat(self, user_message, history, inject_error, context="", extra_instruction=""):
        self.contexts.append(context)
        return {"text": f"reply {len(self.contexts)}", "prompt_tokens": 1, "completion_tokens": 1, "code_loc": 0}


@pytest.fixture
def ciel(monkeypatch):
    fake = Recording()
    monkeypatch.setattr(client_mod, "get_mentor_client", lambda: fake)
    monkeypatch.setattr(service_mod, "get_mentor_client", lambda: fake)
    return fake


async def _attempt(client, db_session, auth_headers) -> int:
    db_session.add(Exercise(code="CP-001", title="t", difficulty="Easy", category="c", level="fresher",
                            language="python", summary="s", starter_code="x", hint="h", domain_keywords=[]))
    await db_session.commit()
    return (await client.post("/api/attempts", json={"exercise_code": "CP-001"}, headers=auth_headers)).json()["attempt_id"]


async def _with_history(db_session):
    """A scored past attempt and two rated skills for the signed-in test user."""
    user = (await db_session.execute(select(User).where(User.email == "testuser@example.com"))).scalar_one()
    ex = (await db_session.execute(select(Exercise))).scalar_one()
    past = Attempt(user_id=user.id, exercise_id=ex.id, status="scored", score=70.0)
    db_session.add(past); await db_session.flush()
    db_session.add(FluencyReport(attempt_id=past.id, understanding_score=0, hypothesis_score=0, explanation_score=0,
                                 overall_score=70.0, feedback={}))
    db_session.add_all([LearnerSkill(user_id=user.id, skill="hash-map", rating=1080.0, attempts=3),
                        LearnerSkill(user_id=user.id, skill="graph", rating=1010.0, attempts=2),
                        LearnerSkill(user_id=user.id, skill="concurrency", rating=930.0, attempts=2)])
    await db_session.commit()


async def _ask(client, aid, auth_headers):
    r = await client.post(f"/api/attempts/{aid}/mentor", json={"message": "where do I start?"}, headers=auth_headers)
    assert r.status_code == 200
    return r.json()["reply"]


async def test_a_new_student_gets_no_learner_block(client, db_session, auth_headers, ciel):
    aid = await _attempt(client, db_session, auth_headers)
    await _ask(client, aid, auth_headers)
    assert "LEARNER PROFILE" not in ciel.contexts[0]


async def test_the_brief_follows_the_exercise_context_without_personal_data(client, db_session, auth_headers, ciel):
    aid = await _attempt(client, db_session, auth_headers)
    await _with_history(db_session)
    await _ask(client, aid, auth_headers)
    context = ciel.contexts[0]
    assert context.index("CURRENT EXERCISE CONTEXT") < context.index("LEARNER PROFILE")
    assert "Never quote ratings" in context
    assert "The learner has 1 scored exercise(s)." in context
    assert "Strongest skills: Hash map (1080, good); Graphs (1010, average)." in context
    assert "Skills to practise: Concurrency (930, needs practice)." in context
    assert "testuser@example.com" not in context and "Test User" not in context


async def test_the_guard_retry_keeps_the_brief(client, db_session, auth_headers, ciel, monkeypatch):
    calls = []

    async def solves_first_reply(db, exercise_id, text):
        calls.append(text)
        return text == "reply 1"

    monkeypatch.setattr(service_mod.guard, "solves_exercise", solves_first_reply)
    aid = await _attempt(client, db_session, auth_headers)
    await _with_history(db_session)
    assert await _ask(client, aid, auth_headers) == "reply 2"
    assert len(ciel.contexts) == 2 and all("LEARNER PROFILE" in c for c in ciel.contexts)


async def test_a_profile_error_does_not_break_ciel(client, db_session, auth_headers, ciel, monkeypatch, caplog):
    async def broken(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(service_mod, "profile", broken)
    aid = await _attempt(client, db_session, auth_headers)
    assert await _ask(client, aid, auth_headers) == "reply 1"
    assert "LEARNER PROFILE" not in ciel.contexts[0]
    assert "learner profile failed" in caplog.text
