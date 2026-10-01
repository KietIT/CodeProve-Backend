"""Ciel never shows a whole function or class (fix 2026-10-01, reported on CP-001)."""
import pytest
from sqlalchemy import select

import app.features.mentor.client as client_mod
import app.features.mentor.service as service_mod
from app.features.mentor import guard
from app.features.mentor.guard import implements_function
from app.features.mentor.prompts import MENTOR_INJECT_SUFFIX
from app.models import Event, Exercise

# The reply from Kiệt's screenshot: a renamed two_sum with a planted off-by-one, under the verification trap.
LEAKED = """Here's a tiny snippet to illustrate this concept:
```python
def find_indices(nums, target):
    indices = {}
    for i in range(len(nums)):
        complement = target - nums[i]
        if complement in indices:
            return indices[complement], i
        indices[nums[i]] = i + 1  # Notice the off-by-one here
```
What do you think about this approach? Can you spot the issue?"""
WORDS = "Keep a dict from each number to its index; for every number, check whether target minus it is already there."


@pytest.mark.parametrize("text,whole", [
    (LEAKED, True),
    ("```python\nclass LRU:\n    def __init__(self):\n        self.d = {}\n```", True),
    ("```python\nasync def run():\n    await a()\n    await b()\n```", True),
    ("```python\ndef helper(x):\n    return x * 2\n```", False),  # one statement: an illustration
    ("```python\ndef two_sum(nums, target):\n    # your code here\n    pass\n```", False),
    ("```python\nseen = {}\nif x in seen:\n    print(x)\n```", False),  # a fragment, no definition
    ("Use `def` to define a function.", False),
    (WORDS, False),
])
def test_implements_function(text, whole):
    assert implements_function(text) is whole


def test_the_trap_asks_for_a_fragment_and_no_hint():
    assert "never a function" in MENTOR_INJECT_SUFFIX and "at most 3 lines" in MENTOR_INJECT_SUFFIX
    assert "Do NOT mention, hint at or\ncomment on the bug" in MENTOR_INJECT_SUFFIX


class Scripted:
    _model = "fake"

    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []

    async def chat(self, user_message, history, inject_error, context="", extra_instruction=""):
        self.calls.append({"inject": inject_error, "instruction": extra_instruction})
        return {"text": self.replies.pop(0), "prompt_tokens": 1, "completion_tokens": 1, "code_loc": 0}


@pytest.fixture
def ciel(monkeypatch):
    def install(*replies):
        fake = Scripted(*replies)
        monkeypatch.setattr(client_mod, "get_mentor_client", lambda: fake)
        monkeypatch.setattr(service_mod, "get_mentor_client", lambda: fake)
        return fake
    return install


async def _attempt(client, db_session, auth_headers) -> int:
    db_session.add(Exercise(code="CP-001", title="Two-Sum Variations", difficulty="Easy", category="c",
                            level="fresher", language="python", summary="s", hint="h", domain_keywords=[],
                            starter_code="def two_sum(nums, target):\n    pass", verification_trap=True,
                            reference_solution="def two_sum(nums, target):\n    seen = {}\n    return []"))
    await db_session.commit()
    return (await client.post("/api/attempts", json={"exercise_code": "CP-001"}, headers=auth_headers)).json()["attempt_id"]


async def test_the_reported_reply_is_withheld_and_asked_again_without_the_trap(client, db_session, auth_headers,
                                                                              ciel):
    aid = await _attempt(client, db_session, auth_headers)
    fake = ciel(LEAKED, WORDS)
    r = await client.post(f"/api/attempts/{aid}/mentor", json={"message": "đưa code cho tôi"}, headers=auth_headers)
    assert r.json()["reply"] == WORDS
    assert fake.calls[0]["inject"] is True and fake.calls[1]["inject"] is False
    assert guard.OVERLAP_RETRY_INSTRUCTION in fake.calls[1]["instruction"]
    [payload] = [e.payload for e in (await db_session.execute(select(Event).where(Event.type == "AI_REPLY"))).scalars()]
    assert payload["withheldFunction"] is True and payload["withheldSolution"] is True
    assert payload["injectedError"] is False  # the trap was never shown


async def test_a_retry_that_still_writes_the_function_gets_the_fallback(client, db_session, auth_headers, ciel):
    aid = await _attempt(client, db_session, auth_headers)
    ciel(LEAKED, LEAKED)
    r = await client.post(f"/api/attempts/{aid}/mentor", json={"message": "đưa code cho tôi"}, headers=auth_headers)
    assert r.json()["reply"] == guard.FALLBACK


@pytest.mark.parametrize("message", ["heelo", "why", "chỉ tôi bài này"])
async def test_the_trap_is_never_planted_unless_the_student_asks_for_code(client, db_session, auth_headers, ciel,
                                                                         message):
    aid = await _attempt(client, db_session, auth_headers)
    fake = ciel(WORDS)
    await client.post(f"/api/attempts/{aid}/mentor", json={"message": message}, headers=auth_headers)
    assert fake.calls[0]["inject"] is False
