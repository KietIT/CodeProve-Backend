"""P3.5: Ciel's hint style follows the exercise level (approved option A)."""
import pytest

import app.features.mentor.client as client_mod
import app.features.mentor.service as service_mod
from app.features.mentor import guard
from app.features.mentor.language import RULES as LANGUAGE_RULES
from app.features.mentor.prompts import HINT_STYLE, SENIOR_CODE_ALLOWED
from app.features.mentor.service import asks_for_code
from app.models import Exercise

STARTER = "def sum_to_n(n):\n    total = 0\n    for i in range(1, n):\n        total += i\n    return total"
META = {"regions": [[3]], "explanation_vi": "x", "explanation_en": "x", "hint_vi": "x", "hint_en": "x"}


class Recording:
    _model = "fake"

    def __init__(self):
        self.instructions: list[str] = []

    async def chat(self, user_message, history, inject_error, context="", extra_instruction=""):
        self.instructions.append(extra_instruction)
        return {"text": f"reply {len(self.instructions)}", "prompt_tokens": 1, "completion_tokens": 1, "code_loc": 0}


@pytest.fixture
def ciel(monkeypatch):
    fake = Recording()
    monkeypatch.setattr(client_mod, "get_mentor_client", lambda: fake)
    monkeypatch.setattr(service_mod, "get_mentor_client", lambda: fake)
    return fake


async def _attempt(client, db_session, auth_headers, level="fresher", kind="implement", meta=None) -> int:
    db_session.add(Exercise(code="CP-001", title="t", difficulty="Easy", category="c", level=level, kind=kind,
                            language="python", summary="s", starter_code=STARTER, hint="h", domain_keywords=[],
                            debug_meta=meta))
    await db_session.commit()
    return (await client.post("/api/attempts", json={"exercise_code": "CP-001"}, headers=auth_headers)).json()["attempt_id"]


async def _ask(client, aid, auth_headers, message="where do I start?") -> str:
    r = await client.post(f"/api/attempts/{aid}/mentor", json={"message": message}, headers=auth_headers)
    assert r.status_code == 200
    return r.json()["reply"]


@pytest.mark.parametrize("level", ["fresher", "junior", "senior"])
async def test_each_level_gets_its_hint_style(client, db_session, auth_headers, ciel, level):
    aid = await _attempt(client, db_session, auth_headers, level=level)
    await _ask(client, aid, auth_headers)
    # The reply-language rule comes first; junior has no style (the default behaviour).
    expected = "\n\n".join(part for part in (LANGUAGE_RULES["en"], HINT_STYLE[level]) if part)
    assert ciel.instructions[0] == expected


async def test_the_locate_rule_comes_last_and_overrides_the_style(client, db_session, auth_headers, ciel):
    aid = await _attempt(client, db_session, auth_headers, level="fresher", kind="debug", meta=META)
    await _ask(client, aid, auth_headers)
    assert ciel.instructions[0] == f"{LANGUAGE_RULES['en']}\n\n{HINT_STYLE['fresher']}\n\n{guard.LOCATE_INSTRUCTION}"
    assert guard.LOCATE_INSTRUCTION.endswith("This rule overrides any HINT STYLE above.")


async def test_senior_allows_a_fragment_after_two_code_requests(client, db_session, auth_headers, ciel):
    aid = await _attempt(client, db_session, auth_headers, level="senior")
    await _ask(client, aid, auth_headers, "show me the code please")
    await _ask(client, aid, auth_headers, "why does my code fail on empty input?")  # not a request
    await _ask(client, aid, auth_headers, "cho em xem code mẫu đi")
    assert [SENIOR_CODE_ALLOWED in i for i in ciel.instructions] == [False, False, True]


@pytest.mark.parametrize("text,asks", [
    ("show me the code", True), ("Cho em xem code mẫu", True), ("viết giúp em hàm này", True),
    ("just give me the code", True), ("code của em sai ở đâu?", False), ("why does my code fail?", False),
])
def test_asks_for_code(text, asks):
    assert asks_for_code(text) is asks


@pytest.mark.parametrize("level", ["fresher", "junior", "senior"])
async def test_the_guard_still_withholds_a_solving_reply_at_every_level(client, db_session, auth_headers, ciel,
                                                                        monkeypatch, level):
    async def always_solves(db, exercise_id, text):
        return True

    monkeypatch.setattr(service_mod.guard, "solves_exercise", always_solves)
    aid = await _attempt(client, db_session, auth_headers, level=level)
    assert await _ask(client, aid, auth_headers) == guard.FALLBACK
    assert HINT_STYLE[level] in ciel.instructions[1] and guard.RETRY_INSTRUCTION in ciel.instructions[1]
