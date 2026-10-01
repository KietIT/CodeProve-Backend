"""Ciel replies in the language of the student's latest message (fix 2026-10-01)."""
import pytest

import app.features.mentor.client as client_mod
import app.features.mentor.service as service_mod
from app.features.mentor.client import chat_messages
from app.features.mentor.language import RULES, detect, reply_language
from app.models import Exercise


@pytest.mark.parametrize("text,language", [
    ("chỉ tôi bài này", "vi"), ("đưa code cho tôi", "vi"), ("Sao code em sai?", "vi"),
    ("chi toi bai nay voi", "vi"),  # unaccented Vietnamese
    ("hello", "en"), ("How do I count words?", "en"), ("give me the code", "en"),
    ("ok", None), ("123", None), ("```python\nprint(1)\n```", None), ("", None),
    ("tại sao `text.split()` lại cắt theo khoảng trắng", "vi"),
    ("what does `đ` mean", "en"),  # a Vietnamese letter inside inline code does not count
])
def test_detect(text, language):
    assert detect(text) == language


def test_a_message_that_says_too_little_keeps_the_previous_language():
    assert reply_language("ok", ["hello", "chỉ tôi bài này"]) == "vi"
    assert reply_language("def f(): pass", ["giúp tôi", "thanks a lot"]) == "en"
    assert reply_language("ok", []) is None


class Recording:
    _model = "fake"

    def __init__(self):
        self.calls: list[dict] = []

    async def chat(self, user_message, history, inject_error, context="", extra_instruction=""):
        self.calls.append({"history": list(history), "instruction": extra_instruction})
        return {"text": "a reply", "prompt_tokens": 1, "completion_tokens": 1, "code_loc": 0}


@pytest.fixture
def ciel(monkeypatch):
    fake = Recording()
    monkeypatch.setattr(client_mod, "get_mentor_client", lambda: fake)
    monkeypatch.setattr(service_mod, "get_mentor_client", lambda: fake)
    return fake


async def test_switching_to_vietnamese_mid_attempt_flips_the_rule(client, db_session, auth_headers, ciel):
    db_session.add(Exercise(code="CP-006", title="t", difficulty="Easy", category="c", level="junior",
                            language="python", summary="s", starter_code="x", hint="h", domain_keywords=[]))
    await db_session.commit()
    aid = (await client.post("/api/attempts", json={"exercise_code": "CP-006"}, headers=auth_headers)).json()["attempt_id"]
    for message in ("hello", "chỉ tôi bài này", "ok"):
        r = await client.post(f"/api/attempts/{aid}/mentor", json={"message": message}, headers=auth_headers)
        assert r.status_code == 200
    rules = [c["instruction"].split("\n\n")[0] for c in ciel.calls]
    assert rules == [RULES["en"], RULES["vi"], RULES["vi"]]  # "ok" keeps Vietnamese
    assert ciel.calls[1]["history"][0] == {"role": "user", "content": "hello"}  # English history, Vietnamese rule


def test_the_rule_is_sent_after_the_history():
    history = [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "Hi there!"}]
    msgs = chat_messages("chỉ tôi bài này", history, inject_error=False, context="EX", extra_instruction=RULES["vi"])
    assert [m["role"] for m in msgs] == ["system", "user", "assistant", "system", "user"]
    assert msgs[3]["content"] == RULES["vi"]
