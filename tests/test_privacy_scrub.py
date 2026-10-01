"""P3.7: personal data is scrubbed from what is sent to OpenAI, and OpenAI is told not to store it."""
import json

import pytest

import app.features.mentor.client as client_mod
from app.features.mentor.prompts import MENTOR_SYSTEM
from app.features.privacy.scrub import scrub
from app.models import Exercise


@pytest.mark.parametrize("text,expected", [
    ("mail me at an.nguyen+cp@fpt.edu.vn please", "mail me at [email] please"),
    ("gọi 0912345678 hoặc +84912345678", "gọi [số điện thoại] hoặc [số điện thoại]"),
    ("em là trần  văn AN nè", "em là [tên] nè"),
    ("assert f(0912) == 3", "assert f(0912) == 3"),  # short numbers are not phones
    ("", ""), (None, ""),
])
def test_scrub(text, expected):
    assert scrub(text, ["Trần Văn An"]) == expected


def test_only_whole_names_of_two_words_or_more():
    assert scrub("An và Trần Văn", ["Trần Văn An"]) == "An và Trần Văn"  # partial names stay
    assert scrub("an = 1", ["An"]) == "an = 1"  # a one-word name could be code
    assert scrub("Trần Văn Anh", ["Trần Văn An"]) == "Trần Văn Anh"  # whole words only


class _RecordingOpenAI:
    def __init__(self):
        self.requests: list[dict] = []
        outer = self

        class Completions:
            async def create(self, **kw):
                outer.requests.append(kw)
                content = json.dumps({"correct": True, "note": "ok", "level": 2, "evidence": "e"}) \
                    if "response_format" in kw else "a hint"
                usage = type("U", (), {"prompt_tokens": 10, "completion_tokens": 2, "prompt_tokens_details": None})()
                msg = type("M", (), {"content": content})()
                return type("R", (), {"choices": [type("C", (), {"message": msg})()], "usage": usage})()

        self.chat = type("Chat", (), {"completions": Completions()})()


@pytest.fixture
def openai(monkeypatch):
    fake = _RecordingOpenAI()
    mc = client_mod.MentorClient.__new__(client_mod.MentorClient)
    mc._client, mc._model = fake, "gpt-4o-mini"
    monkeypatch.setattr(client_mod, "_singleton", mc)
    return fake


async def _attempt(client, db_session, auth_headers) -> int:
    db_session.add(Exercise(code="CP-001", title="t", difficulty="Easy", category="c", level="junior",
                            language="python", summary="s", starter_code="x", hint="h", domain_keywords=[]))
    await db_session.commit()
    return (await client.post("/api/attempts", json={"exercise_code": "CP-001"}, headers=auth_headers)).json()["attempt_id"]


async def test_ciel_never_sends_personal_data_and_asks_not_to_store(client, db_session, auth_headers, openai):
    aid = await _attempt(client, db_session, auth_headers)
    # "Test User" is the name of the conftest account.
    body = {"message": "Em là test user, email testuser@example.com, sđt 0987654321. Sao sai?",
            "code": "OWNER = 'testuser@example.com'\ndef f():\n    return 1"}
    first = await client.post(f"/api/attempts/{aid}/mentor", json=body, headers=auth_headers)
    assert first.status_code == 200
    await client.post(f"/api/attempts/{aid}/mentor", json={"message": "còn test user hỏi tiếp"}, headers=auth_headers)
    for request in openai.requests:
        assert request["store"] is False
        sent = [m["content"] for m in request["messages"] if m["role"] != "system"]
        assert not any("example.com" in s or "0987654321" in s or "test user" in s.lower() for s in sent), sent
        assert request["messages"][0]["content"].startswith(MENTOR_SYSTEM)  # our system prompt is untouched
    question = openai.requests[0]["messages"][-1]["content"]
    assert "Em là [tên], email [email], sđt [số điện thoại]." in question
    assert "OWNER = '[email]'\ndef f():\n    return 1" in question  # the code keeps its shape
    # The second turn's history (from the stored log) is scrubbed on the way out too.
    assert "[email]" in openai.requests[1]["messages"][1]["content"]


async def test_judges_scrub_too_and_ask_not_to_store(client, db_session, auth_headers, openai):
    aid = await _attempt(client, db_session, auth_headers)
    r = await client.post(f"/api/attempts/{aid}/hypothesis", headers=auth_headers,
                          json={"text": "Test User nghĩ dùng dict, liên hệ testuser@example.com"})
    assert r.status_code == 200
    [request] = openai.requests
    assert request["store"] is False
    user_content = request["messages"][1]["content"]
    assert "[tên] nghĩ dùng dict, liên hệ [email]" in user_content and "example.com" not in user_content
