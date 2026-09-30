"""P3.1: Ciel sees the last exchanges of the same attempt."""
import pytest

import app.features.mentor.client as client_mod
import app.features.mentor.service as service_mod
from app.features.mentor.memory import MAX_EXCHANGES, MAX_MESSAGE_CHARS, MAX_TOTAL_CHARS, attempt_history


class Recording:
    _model = "fake"

    def __init__(self):
        self.histories, self.n = [], 0

    async def chat(self, user_message, history, inject_error, context="", extra_instruction=""):
        self.histories.append(list(history))
        self.n += 1
        text = f"reply {self.n}"
        return {"text": text, "prompt_tokens": 1, "completion_tokens": 1, "code_loc": 0}


@pytest.fixture
def ciel(monkeypatch):
    fake = Recording()
    monkeypatch.setattr(client_mod, "get_mentor_client", lambda: fake)
    monkeypatch.setattr(service_mod, "get_mentor_client", lambda: fake)
    return fake


async def _attempt(client, db_session, auth_headers, code="CP-001") -> int:
    from sqlalchemy import select

    from app.models import Exercise

    if not (await db_session.execute(select(Exercise).where(Exercise.code == code))).scalar_one_or_none():
        db_session.add(Exercise(code=code, title="t", difficulty="Easy", category="c", level="fresher",
                                language="python", summary="s", starter_code="x", hint="h", domain_keywords=[]))
        await db_session.commit()
    return (await client.post("/api/attempts", json={"exercise_code": code}, headers=auth_headers)).json()["attempt_id"]


async def _ask(client, aid, auth_headers, message):
    r = await client.post(f"/api/attempts/{aid}/mentor", json={"message": message}, headers=auth_headers)
    assert r.status_code == 200


async def test_the_second_question_sees_the_first_exchange(client, db_session, auth_headers, ciel):
    aid = await _attempt(client, db_session, auth_headers)
    await _ask(client, aid, auth_headers, "what is a hash map?")
    await _ask(client, aid, auth_headers, "and how do I use it here?")
    assert ciel.histories[0] == []
    assert ciel.histories[1] == [{"role": "user", "content": "what is a hash map?"},
                                 {"role": "assistant", "content": "reply 1"}]


async def test_only_this_attempts_messages_are_remembered(client, db_session, auth_headers, ciel):
    first = await _attempt(client, db_session, auth_headers)
    await _ask(client, first, auth_headers, "question in attempt one")
    second = await _attempt(client, db_session, auth_headers)
    await _ask(client, second, auth_headers, "question in attempt two")
    assert ciel.histories[-1] == []


async def test_history_keeps_the_last_exchanges_within_the_caps(db_session):
    from app.models import Attempt, Exercise, PromptLog, User

    user = User(full_name="u", email="m@example.com", password_hash="x")
    ex = Exercise(code="CP-002", title="t", difficulty="Easy", category="c", level="fresher", language="python",
                  summary="s", starter_code="x", hint="h", domain_keywords=[])
    db_session.add_all([user, ex])
    await db_session.flush()
    attempt = Attempt(user_id=user.id, exercise_id=ex.id, status="in_progress")
    db_session.add(attempt)
    await db_session.flush()
    for i in range(MAX_EXCHANGES + 2):
        db_session.add(PromptLog(attempt_id=attempt.id, prompt=f"q{i}", response=f"a{i}", model="m", tokens=1))
    db_session.add(PromptLog(attempt_id=attempt.id, prompt="x" * (MAX_MESSAGE_CHARS + 50), response="long",
                             model="m", tokens=1))
    await db_session.commit()

    history = await attempt_history(db_session, attempt.id)
    assert len(history) == 2 * MAX_EXCHANGES
    assert history[-2]["content"].endswith("…") and len(history[-2]["content"]) == MAX_MESSAGE_CHARS + 1
    assert history[0]["content"] == f"q{3}"  # the oldest ones dropped, order kept
    assert sum(len(m["content"]) for m in history) <= MAX_TOTAL_CHARS
