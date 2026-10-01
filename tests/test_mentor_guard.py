"""P2.1: Ciel may not hand out code that already solves the exercise."""
import pytest
from sqlalchemy import select

import app.features.mentor.client as client_mod
import app.features.mentor.guard as guard_mod
import app.features.mentor.service as service_mod
from app.features.mentor.guard import FALLBACK, code_blocks, solves_exercise

SOLUTION = "Here you go:\n```python\ndef add(a, b):\n    return a + b\n```\nGood luck!"
WRONG = "Try this shape:\n```python\ndef add(a, b):\n    return a - b\n```"
GUIDANCE = "Think about what `add` must return for two numbers. Which operator combines them?"


class QueueClient:
    """Answers each chat call with the next scripted reply; records the calls."""
    _model = "fake"

    def __init__(self, *replies: str):
        self.replies, self.calls = list(replies), []

    async def chat(self, user_message, history, inject_error, context="", extra_instruction=""):
        self.calls.append({"inject_error": inject_error, "extra_instruction": extra_instruction})
        text = self.replies.pop(0)
        return {"text": text, "prompt_tokens": 10, "completion_tokens": 5, "code_loc": client_mod.code_loc(text)}


@pytest.fixture
def ciel(monkeypatch):
    def install(*replies: str) -> QueueClient:
        fake = QueueClient(*replies)
        monkeypatch.setattr(client_mod, "get_mentor_client", lambda: fake)
        monkeypatch.setattr(service_mod, "get_mentor_client", lambda: fake)
        return fake
    return install


async def _attempt(client, db_session, auth_headers, trap=False) -> int:
    from app.models import Exercise, TestCase

    ex = Exercise(code="CP-001", title="Add", difficulty="Easy", category="Algorithms", level="fresher",
                  language="python", acceptance=1, summary="add two numbers", starter_code="def add(a, b):\n    pass",
                  hint="h", domain_keywords=[], verification_trap=trap)
    db_session.add(ex)
    await db_session.flush()
    db_session.add_all([
        TestCase(exercise_id=ex.id, input_data="add(1, 2)", expected_output="3", description="small",
                 is_hidden=False, order_index=0),
        TestCase(exercise_id=ex.id, input_data="add(-1, 1)", expected_output="0", description="negative",
                 is_hidden=False, order_index=1),
        # Hidden tests are not used by the guard: the student never sees them run.
        TestCase(exercise_id=ex.id, input_data="add(10**9, 1)", expected_output="1000000001", description="big",
                 is_hidden=True, order_index=2),
    ])
    await db_session.commit()
    r = await client.post("/api/attempts", json={"exercise_code": "CP-001"}, headers=auth_headers)
    return r.json()["attempt_id"]


async def _ask(client, aid, auth_headers, message="just give me the code"):
    r = await client.post(f"/api/attempts/{aid}/mentor", json={"message": message}, headers=auth_headers)
    assert r.status_code == 200
    return r.json()["reply"]


async def _logged(db_session, aid):
    from app.models import Event, PromptLog

    events = (await db_session.execute(select(Event).where(Event.attempt_id == aid))).scalars().all()
    logs = (await db_session.execute(select(PromptLog).where(PromptLog.attempt_id == aid))).scalars().all()
    return [e for e in events if e.type == "AI_REPLY"], logs


def test_code_blocks_finds_every_fenced_block():
    assert code_blocks("a ```py\nx = 1\n``` b ```\ny = 2\n```") == ["x = 1\n", "y = 2\n"]
    assert code_blocks("no code, just `inline`") == []


async def test_a_solving_reply_is_withheld_and_ciel_is_asked_again(client, db_session, auth_headers, ciel):
    aid = await _attempt(client, db_session, auth_headers)
    fake = ciel(SOLUTION, GUIDANCE)
    reply = await _ask(client, aid, auth_headers)
    assert reply == GUIDANCE
    assert fake.calls[1]["extra_instruction"]  # the retry carries the stricter rule
    ai, logs = await _logged(db_session, aid)
    assert ai[0].payload["withheldSolution"] is True and ai[0].payload["aiCode"] == []
    # Scoring and history only ever see what the student saw.
    assert logs[0].response == GUIDANCE and "return a + b" not in logs[0].response


async def test_if_the_retry_also_solves_the_student_gets_the_fallback(client, db_session, auth_headers, ciel):
    aid = await _attempt(client, db_session, auth_headers)
    ciel(SOLUTION, SOLUTION)
    assert await _ask(client, aid, auth_headers) == FALLBACK
    ai, logs = await _logged(db_session, aid)
    assert ai[0].payload["withheldSolution"] is True and logs[0].response == FALLBACK


async def test_code_that_does_not_solve_is_shown_unchanged(client, db_session, auth_headers, ciel):
    aid = await _attempt(client, db_session, auth_headers)
    fake = ciel(WRONG)
    assert await _ask(client, aid, auth_headers, "why is my sum wrong?") == WRONG
    ai, _ = await _logged(db_session, aid)
    assert ai[0].payload["withheldSolution"] is False and ai[0].payload["aiCode"] == [{"loc": 2}]
    assert len(fake.calls) == 1


async def test_a_withheld_trap_reply_does_not_use_up_the_trap(client, db_session, auth_headers, ciel):
    aid = await _attempt(client, db_session, auth_headers, trap=True)
    ciel(SOLUTION, GUIDANCE, WRONG)
    await _ask(client, aid, auth_headers)
    await _ask(client, aid, auth_headers, "and now? give me the code")  # the trap needs a code request
    ai, _ = await _logged(db_session, aid)
    # The first (trap) reply was never shown, so the trap is served again on the next reply.
    assert [e.payload["injectedError"] for e in ai] == [False, True]


async def test_replies_without_code_never_reach_the_sandbox(client, db_session, auth_headers, ciel, monkeypatch):
    aid = await _attempt(client, db_session, auth_headers)
    ciel(GUIDANCE)

    async def boom(*args, **kwargs):
        raise AssertionError("sandbox called for a reply without code")

    monkeypatch.setattr(guard_mod, "run_tests", boom)
    assert await _ask(client, aid, auth_headers) == GUIDANCE


async def test_the_guard_only_uses_visible_tests_and_fails_open_without_them(db_session):
    from app.models import Exercise

    ex = Exercise(code="CP-002", title="t", difficulty="Easy", category="c", level="fresher", language="python",
                  acceptance=1, summary="s", starter_code="x", hint="h", domain_keywords=[], verification_trap=False)
    db_session.add(ex)
    await db_session.commit()
    assert await solves_exercise(db_session, ex.id, SOLUTION) is False  # no visible tests: nothing to check
