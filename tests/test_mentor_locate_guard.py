"""P2.2 follow-up: Ciel may not point at the bug of a debug exercise before the student has located it."""
import pytest
from sqlalchemy import select

import app.features.mentor.client as client_mod
import app.features.mentor.service as service_mod
from app.features.mentor.guard import BUG_FALLBACK, LOCATE_INSTRUCTION, reveals_bug

STARTER = "def sum_to_n(n):\n    total = 0\n    for i in range(1, n):   # bug\n        total += i\n    return total"
SERVED = "def sum_to_n(n):\n    total = 0\n    for i in range(1, n):\n        total += i\n    return total"
META = {"regions": [[3]], "explanation_vi": "x", "explanation_en": "x", "hint_vi": "h", "hint_en": "h"}
QUOTES_BUG = "Look at `for i in range(1, n):` - it stops too early."
NAMES_LINE = "Kiểm tra lại dòng 3 nhé."
HINT = "Try sum_to_n(3) by hand, then run it in the Visualizer: which value is never added?"


class QueueClient:
    _model = "fake"

    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []

    async def chat(self, user_message, history, inject_error, context="", extra_instruction=""):
        self.calls.append(extra_instruction)
        text = self.replies.pop(0)
        return {"text": text, "prompt_tokens": 1, "completion_tokens": 1, "code_loc": client_mod.code_loc(text)}


@pytest.fixture
def ciel(monkeypatch):
    def install(*replies):
        fake = QueueClient(*replies)
        monkeypatch.setattr(client_mod, "get_mentor_client", lambda: fake)
        monkeypatch.setattr(service_mod, "get_mentor_client", lambda: fake)
        return fake
    return install


async def _attempt(client, db_session, auth_headers, kind="debug") -> int:
    from app.models import Exercise

    db_session.add(Exercise(code="CP-004", title="t", difficulty="Easy", category="Debugging", level="fresher",
                            language="python", summary="sum 1..n", kind=kind, starter_code=STARTER, hint="h",
                            domain_keywords=[], debug_meta=META if kind == "debug" else None))
    await db_session.commit()
    return (await client.post("/api/attempts", json={"exercise_code": "CP-004"}, headers=auth_headers)).json()["attempt_id"]


async def _ask(client, aid, auth_headers):
    r = await client.post(f"/api/attempts/{aid}/mentor", json={"message": "where is the bug?"}, headers=auth_headers)
    assert r.status_code == 200
    return r.json()["reply"]


async def _replies(db_session, aid):
    from app.models import Event
    rows = (await db_session.execute(select(Event).where(Event.attempt_id == aid, Event.type == "AI_REPLY")
                                     .order_by(Event.id))).scalars().all()
    return [r.payload for r in rows]


def test_quoting_a_bug_line_or_naming_its_number_reveals_the_bug():
    assert reveals_bug(QUOTES_BUG, SERVED, [[3]])
    assert reveals_bug("the problem is on line 3", SERVED, [[3]])
    assert reveals_bug(NAMES_LINE, SERVED, [[3]])
    assert reveals_bug("Xem các dòng 2-4", SERVED, [[3]])      # a range covering the bug
    assert not reveals_bug(HINT, SERVED, [[3]])
    assert not reveals_bug("line 5 returns the total", SERVED, [[3]])
    assert not reveals_bug("total = 0 starts the sum", SERVED, [[3]])  # a line outside the bug


async def test_before_locating_ciel_is_told_to_hint_and_a_reveal_is_asked_again(client, db_session, auth_headers,
                                                                                ciel):
    aid = await _attempt(client, db_session, auth_headers)
    fake = ciel(QUOTES_BUG, HINT)
    assert await _ask(client, aid, auth_headers) == HINT
    assert LOCATE_INSTRUCTION in fake.calls[0] and LOCATE_INSTRUCTION in fake.calls[1]
    assert (await _replies(db_session, aid))[0]["withheldBugLocation"] is True


async def test_a_second_reveal_becomes_the_fallback(client, db_session, auth_headers, ciel):
    aid = await _attempt(client, db_session, auth_headers)
    ciel(NAMES_LINE, QUOTES_BUG)
    assert await _ask(client, aid, auth_headers) == BUG_FALLBACK


async def test_a_wrong_or_skipped_location_keeps_the_bug_hidden(client, db_session, auth_headers, ciel):
    aid = await _attempt(client, db_session, auth_headers)
    await client.post(f"/api/attempts/{aid}/debug/locate", headers=auth_headers, json={"lines": [4], "reason": "x"})
    fake = ciel(QUOTES_BUG, HINT)
    assert await _ask(client, aid, auth_headers) == HINT
    assert LOCATE_INSTRUCTION in fake.calls[0]


async def test_once_located_correctly_ciel_may_talk_about_the_bug(client, db_session, auth_headers, ciel):
    aid = await _attempt(client, db_session, auth_headers)
    await client.post(f"/api/attempts/{aid}/debug/locate", headers=auth_headers, json={"lines": [3], "reason": "x"})
    fake = ciel(QUOTES_BUG)
    assert await _ask(client, aid, auth_headers) == QUOTES_BUG
    # One call, without the locate rule (the fresher hint style is still there, P3.5).
    assert len(fake.calls) == 1 and LOCATE_INSTRUCTION not in fake.calls[0]
    assert (await _replies(db_session, aid))[0]["withheldBugLocation"] is False


async def test_implement_exercises_are_not_affected(client, db_session, auth_headers, ciel):
    aid = await _attempt(client, db_session, auth_headers, kind="implement")
    fake = ciel(QUOTES_BUG)
    assert await _ask(client, aid, auth_headers) == QUOTES_BUG
    assert len(fake.calls) == 1 and LOCATE_INSTRUCTION not in fake.calls[0]
