"""P3.6: Ciel's prompt is laid out so consecutive turns share a cacheable prefix."""
import pytest
from sqlalchemy import select

import app.features.mentor.client as client_mod
import app.features.mentor.service as service_mod
from app.features.mentor.client import chat_messages
from app.features.mentor.prompts import MENTOR_INJECT_SUFFIX, MENTOR_SYSTEM
from app.models import Event, Exercise

HISTORY = [{"role": "user", "content": "q1"}, {"role": "assistant", "content": "a1"}]


def test_static_first_then_history_then_turn_instructions_then_question():
    msgs = chat_messages("q2", HISTORY, inject_error=True, context="EXERCISE", extra_instruction="LOCATE")
    assert [m["role"] for m in msgs] == ["system", "user", "assistant", "system", "user"]
    assert msgs[0]["content"] == f"{MENTOR_SYSTEM}\n\nEXERCISE"
    assert msgs[3]["content"] == f"{MENTOR_INJECT_SUFFIX.strip()}\n\nLOCATE"
    assert msgs[-1] == {"role": "user", "content": "q2"}


def test_no_turn_message_when_there_is_nothing_for_this_turn():
    msgs = chat_messages("q", [], inject_error=False, context="EXERCISE")
    assert [m["role"] for m in msgs] == ["system", "user"]


class Recording:
    _model = "fake"

    def __init__(self):
        self.calls: list[dict] = []

    async def chat(self, user_message, history, inject_error, context="", extra_instruction=""):
        self.calls.append({"user": user_message, "context": context, "history": list(history)})
        return {"text": f"reply {len(self.calls)}", "prompt_tokens": 1200, "completion_tokens": 10,
                "cached_tokens": 1024, "code_loc": 0}


@pytest.fixture
def ciel(monkeypatch):
    fake = Recording()
    monkeypatch.setattr(client_mod, "get_mentor_client", lambda: fake)
    monkeypatch.setattr(service_mod, "get_mentor_client", lambda: fake)
    return fake


async def _attempt(client, db_session, auth_headers) -> int:
    db_session.add(Exercise(code="CP-001", title="t", difficulty="Easy", category="c", level="junior",
                            language="python", summary="s", starter_code="x", hint="h", domain_keywords=[]))
    await db_session.commit()
    return (await client.post("/api/attempts", json={"exercise_code": "CP-001"}, headers=auth_headers)).json()["attempt_id"]


async def _ask(client, aid, headers, message, code=None):
    body = {"message": message, **({"code": code} if code is not None else {})}
    assert (await client.post(f"/api/attempts/{aid}/mentor", json=body, headers=headers)).status_code == 200


async def test_the_code_goes_with_the_question_and_the_system_context_stays_the_same(
        client, db_session, auth_headers, ciel):
    aid = await _attempt(client, db_session, auth_headers)
    await _ask(client, aid, auth_headers, "first question", "def f():\n    return 1")
    await _ask(client, aid, auth_headers, "second question", "def f():\n    return 2")
    first, second = ciel.calls
    assert first["context"] == second["context"] and "def f()" not in first["context"]
    assert second["user"] == "second question\n\nMy current code:\n```python\ndef f():\n    return 2\n```"
    # History keeps only what was asked, not the code of earlier turns.
    assert second["history"] == [{"role": "user", "content": "first question"},
                                 {"role": "assistant", "content": "reply 1"}]


async def test_no_code_means_just_the_question(client, db_session, auth_headers, ciel):
    aid = await _attempt(client, db_session, auth_headers)
    await _ask(client, aid, auth_headers, "only a question", "   ")
    assert ciel.calls[0]["user"] == "only a question"


async def test_cached_tokens_are_recorded(client, db_session, auth_headers, ciel):
    aid = await _attempt(client, db_session, auth_headers)
    await _ask(client, aid, auth_headers, "a question")
    prompt = (await db_session.execute(select(Event).where(Event.type == "PROMPT"))).scalar_one()
    assert prompt.payload["promptTokens"] == 1200 and prompt.payload["cachedTokens"] == 1024


class _Usage:
    prompt_tokens, completion_tokens = 1500, 20

    class prompt_tokens_details:  # noqa: N801 - mirrors the OpenAI SDK attribute
        cached_tokens = 1280


async def test_the_client_reads_cached_tokens_from_the_usage():
    class _Completions:
        async def create(self, **kwargs):
            self.kwargs = kwargs
            choice = type("C", (), {"message": type("M", (), {"content": "hello"})()})()
            return type("R", (), {"choices": [choice], "usage": _Usage()})()

    mc = client_mod.MentorClient.__new__(client_mod.MentorClient)
    completions = _Completions()
    mc._client = type("O", (), {"chat": type("Ch", (), {"completions": completions})()})()
    mc._model = "gpt-4o-mini"
    out = await mc.chat("q", HISTORY, inject_error=False, context="EX")
    assert out["cached_tokens"] == 1280 and out["prompt_tokens"] == 1500
    assert [m["role"] for m in completions.kwargs["messages"]] == ["system", "user", "assistant", "user"]
