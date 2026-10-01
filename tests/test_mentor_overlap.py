"""Ciel cannot give the solution away piece by piece (fix 2026-10-01, reported on CP-006)."""
import pytest
from sqlalchemy import select

import app.features.mentor.client as client_mod
import app.features.mentor.service as service_mod
from app.features.content.schema import CONTENT_DIR, load_content_file
from app.features.mentor import guard
from app.features.mentor.overlap import OVERLAP_THRESHOLD, coverage, snippets, tokens
from app.features.mentor.overlap_check import check
from app.models import Event, Exercise

CP006 = load_content_file(CONTENT_DIR / "CP-006.json").reference_solution
# The replies from Kiệt's screenshots (2026-10-01).
REPLY_SPLIT = "For example, you might use `split()`:\n```python\nwords = text.lower().split()\n```\nHow would you count?"
REPLY_COUNT = ("Here's a tiny example:\n```python\nword_counts = {}\nfor word in words:\n"
               "    word_counts[word] = word_counts.get(word, 0) + 1\n```\nWhat do you think?")
REPLY_OTHER_CONTEXT = ("In a different context:\n```python\ncounts = {}\nfor item in ['apple', 'banana']:\n"
                       "    counts[item] = counts.get(item, 0) + 1\n```")
WORDS_ONLY = "Lowercase the text, split it into words, then keep a running count per word in a dict."


def test_identifiers_are_renamed_but_keywords_builtins_and_methods_stay():
    assert tokens("counts[w] = counts.get(w, 0) + 1") == \
        ["ID", "[", "ID", "]", "=", "ID", ".", "get", "(", "ID", ",", "0", ")", "+", "1"]
    assert tokens("for x in range(len(s)): print('hi')") == \
        ["for", "ID", "in", "range", "(", "len", "(", "ID", ")", ")", ":", "print", "(", "STR", ")"]


def test_snippets_take_fenced_blocks_and_inline_code():
    assert snippets("use `a.b()` then\n```python\nx = 1\n```") == ["x = 1\n", "a.b()"]
    assert snippets("no code here") == []


def test_the_reported_transcript():
    assert coverage(CP006, "", snippets(REPLY_SPLIT)) < OVERLAP_THRESHOLD  # one piece alone is shown
    assert coverage(CP006, "", snippets(REPLY_SPLIT) + snippets(REPLY_COUNT)) >= OVERLAP_THRESHOLD
    assert coverage(CP006, "", snippets(REPLY_OTHER_CONTEXT)) >= OVERLAP_THRESHOLD  # renamed copy counts
    assert coverage(CP006, "", snippets(WORDS_ONLY)) == 0


def test_on_debug_exercises_only_the_fix_counts_not_the_code_the_student_sees():
    reference = "def sum_to_n(n):\n    total = 0\n    for i in range(1, n + 1):\n        total += i\n    return total"
    starter = "def sum_to_n(n):\n    total = 0\n    for i in range(1, n):\n        total += i\n    return total"
    assert coverage(reference, starter, ["for i in range(1, n):"]) == 0  # quoting the student's own code
    assert coverage(reference, starter, ["for i in range(1, n + 1):"]) == 1  # the fix


def test_the_threshold_holds_on_every_exercise():
    failing = [r["code"] for r in check() if not r["ok"]]
    assert failing == []


class Scripted:
    _model = "fake"

    def __init__(self, *replies):
        self.replies, self.instructions = list(replies), []

    async def chat(self, user_message, history, inject_error, context="", extra_instruction=""):
        self.instructions.append(extra_instruction)
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
    db_session.add(Exercise(code="CP-006", title="Count Word Frequency", difficulty="Easy", category="c",
                            level="fresher", language="python", summary="s", hint="h", domain_keywords=[],
                            starter_code="def word_count(text):\n    pass", reference_solution=CP006))
    await db_session.commit()
    return (await client.post("/api/attempts", json={"exercise_code": "CP-006"}, headers=auth_headers)).json()["attempt_id"]


async def _ask(client, aid, auth_headers, message):
    r = await client.post(f"/api/attempts/{aid}/mentor", json={"message": message}, headers=auth_headers)
    assert r.status_code == 200
    return r.json()["reply"]


async def _replies(db_session):
    rows = (await db_session.execute(select(Event).where(Event.type == "AI_REPLY").order_by(Event.id))).scalars().all()
    return [r.payload for r in rows]


async def test_the_second_piece_is_withheld_and_ciel_asked_for_words_only(client, db_session, auth_headers, ciel):
    aid = await _attempt(client, db_session, auth_headers)
    ciel(REPLY_SPLIT)
    assert await _ask(client, aid, auth_headers, "chỉ tôi bài này") == REPLY_SPLIT
    fake = ciel(REPLY_COUNT, WORDS_ONLY)
    assert await _ask(client, aid, auth_headers, "đưa code cho tôi") == WORDS_ONLY
    assert guard.OVERLAP_RETRY_INSTRUCTION in fake.instructions[1]
    assert [r["withheldOverlap"] for r in await _replies(db_session)] == [False, True]


async def test_a_retry_that_still_leaks_gets_the_fallback(client, db_session, auth_headers, ciel):
    aid = await _attempt(client, db_session, auth_headers)
    ciel(REPLY_OTHER_CONTEXT, REPLY_OTHER_CONTEXT)
    assert await _ask(client, aid, auth_headers, "give me the code") == guard.FALLBACK
    [payload] = await _replies(db_session)
    assert payload["withheldSolution"] is True and payload["withheldOverlap"] is True


async def test_replies_without_code_are_never_withheld_by_it(client, db_session, auth_headers, ciel):
    aid = await _attempt(client, db_session, auth_headers)
    ciel(REPLY_SPLIT)
    await _ask(client, aid, auth_headers, "hint?")
    ciel(WORDS_ONLY)
    assert await _ask(client, aid, auth_headers, "and then?") == WORDS_ONLY
