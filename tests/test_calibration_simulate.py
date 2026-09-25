import json

import httpx
import pytest
from pydantic import ValidationError

from app.features.calibration.simulate import (Api, Player, Script, State, Step, ai_code, answer_all, chars_added,
                                               load_material, resolve_code, validate_script)
from app.features.content.schema import CONTENT_DIR, load_content_file
from app.features.exercises.starters import student_starter
from app.seed.exercises_seed import EXERCISES


def _script(*steps: dict, exercise: str = "CP-001") -> Script:
    return Script.model_validate({"id": "sim-01", "student": 1, "exercise": exercise, "steps": list(steps)})


def test_a_script_must_end_with_its_only_submit():
    with pytest.raises(ValidationError, match="submit"):
        _script({"at": 1, "do": "run"})
    with pytest.raises(ValidationError, match="submit"):
        _script({"at": 1, "do": "submit"}, {"at": 2, "do": "run"}, {"at": 3, "do": "submit"})


def test_steps_are_ordered_by_time_and_need_their_fields():
    s = _script({"at": 5, "do": "submit"}, {"at": 1, "do": "hypothesis", "text": "dict of seen values"})
    assert [x.do for x in s.steps] == ["hypothesis", "submit"]
    with pytest.raises(ValidationError, match="text"):
        Step(at=1, do="ask")
    with pytest.raises(ValidationError, match="ref"):
        Step(at=1, do="code")
    with pytest.raises(ValidationError, match="code"):
        Step(at=1, do="code", ref="inline")


def test_refs_resolve_to_the_reviewed_content():
    material = load_material("CP-001", CONTENT_DIR)
    content = load_content_file(CONTENT_DIR / "CP-001.json")
    seed = next(e for e in EXERCISES if e["code"] == "CP-001")
    assert resolve_code(Step(at=0, do="code", ref="reference"), material) == content.reference_solution
    assert resolve_code(Step(at=0, do="code", ref="mutant:2"), material) == content.mutants[1].code
    assert resolve_code(Step(at=0, do="code", ref="starter"), material) == student_starter(
        content.starter_for(seed["starter_code"]), seed.get("kind") or "implement")
    assert resolve_code(Step(at=0, do="code", ref="inline", code="x = 1"), material) == "x = 1"
    assert material.entry == "two_sum"


def test_validate_script_rejects_unknown_refs():
    material = load_material("CP-001", CONTENT_DIR)
    bad = _script({"at": 1, "do": "code", "ref": "mutant:9"}, {"at": 2, "do": "submit"})
    assert validate_script(bad, material) == ["step 1: mutant:9 out of range (1-4)"]
    bad = _script({"at": 1, "do": "code", "ref": "solution"}, {"at": 2, "do": "submit"})
    assert validate_script(bad, material) == ["step 1: unknown ref 'solution'"]
    good = _script({"at": 1, "do": "code", "ref": "mutant:4"}, {"at": 2, "do": "submit"})
    assert validate_script(good, material) == []


# ---------- Runner (fake API) ----------

REPLY_WITH_CODE = "Try this:\n```python\ndef two_sum(nums, target):\n    return [0, 1]\n```\nThen test it."


class FakeApi:
    """Records every request and answers like the real endpoints."""

    def __init__(self, reply: str = REPLY_WITH_CODE) -> None:
        self.calls: list[tuple[str, str, dict | None, dict]] = []
        self.reply = reply

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        path = request.url.path
        self.calls.append((request.method, path, body, dict(request.url.params)))
        if path == "/api/auth/signup":
            return httpx.Response(200, json={"access_token": "tok", "user": {}})
        if path == "/api/attempts":
            return httpx.Response(200, json={"attempt_id": 7, "started_at": "now"})
        if path.endswith("/hypothesis"):
            return httpx.Response(200, json={"correct": True, "note": "ok"})
        if path.endswith("/run"):
            return httpx.Response(200, json={"passed": 1, "total": 2, "coverage": 0.5, "cases": [],
                                             "runtime_error": None})
        if path.endswith("/mentor"):
            return httpx.Response(200, json={"reply": self.reply})
        if path.endswith("/submit"):
            return httpx.Response(200, json={"questions": ["Why a dict?", "What if empty?"], "tests": {}})
        if path.endswith("/explain-back"):
            return httpx.Response(200, json={"overall": 71.0, "tier": "Strong", "axes": {"testing": 20.0},
                                             "feedback": {"not_applicable": {"debugging": "no_failure"}}})
        return httpx.Response(200, json={"ok": True})


async def _nosleep(_seconds: float) -> None:
    return None


async def _play(tmp_path, steps: list[dict], reply: str = REPLY_WITH_CODE) -> tuple[FakeApi, State, list[dict]]:
    fake, logs = FakeApi(reply), []
    state = State(tmp_path / "state.json")
    script = Script.model_validate({"id": "sim-01", "student": 3, "exercise": "CP-001", "locale": "vi",
                                    "steps": steps})
    async with httpx.AsyncClient(transport=httpx.MockTransport(fake), base_url="http://api") as client:
        player = Player(script, load_material("CP-001"), Api(client, _nosleep), state, logs.append,
                        speed=float("inf"), sleep=_nosleep, now_ms=lambda: 1000)
        await player.play()
    return fake, state, logs


def _paths(fake: FakeApi) -> list[str]:
    return [f"{m} {p.replace('/api/attempts/7', '')}" for m, p, _, _ in fake.calls]


async def test_a_script_plays_like_the_web_client(tmp_path):
    fake, state, logs = await _play(tmp_path, [
        {"at": 0.5, "do": "hypothesis", "text": "dict of seen numbers, O(n)"},
        {"at": 1, "do": "code", "ref": "mutant:1"},
        {"at": 2, "do": "run"},
        {"at": 3, "do": "ask", "text": "why does [3, 3] fail?", "send_code": True},
        {"at": 4, "do": "away", "seconds": 40},
        {"at": 5, "do": "code", "ref": "reference"},
        {"at": 6, "do": "submit"},
    ])
    assert _paths(fake) == [
        "POST /api/auth/signup", "POST /api/attempts", "POST /events",
        "POST /hypothesis", "POST /events", "POST /snapshots", "POST /run", "POST /mentor",
        "POST /events", "POST /events", "POST /events", "POST /snapshots", "POST /submit",
    ]
    bodies = [b for _, _, b, _ in fake.calls]
    assert bodies[0]["email"] == "calib.sim03@example.com"
    assert bodies[2]["events"][0]["type"] == "OPEN"
    assert bodies[4]["events"][0]["type"] == "CODE_EDIT" and bodies[4]["events"][0]["payload"]["charsAdded"] > 0
    assert bodies[5]["version"] == 1
    assert bodies[7]["code"] == load_material("CP-001").mutants[0]
    assert bodies[8]["events"][0] == {"type": "TAB_HIDDEN", "ts": 1000, "payload": {},
                                      "integrity_flags": ["TAB_HIDDEN"]}
    assert bodies[9]["events"][0]["type"] == "TAB_VISIBLE"
    # /run stored version 2, so the editor's next snapshot is version 3 and stays the latest.
    assert bodies[11]["version"] == 3
    assert fake.calls[-1][3] == {"locale": "vi"}
    record = state.data["sessions"]["sim-01"]
    assert record["status"] == "submitted" and record["attempt_id"] == 7
    assert record["questions"] == ["Why a dict?", "What if empty?"]
    assert [entry["do"] for entry in logs] == ["hypothesis", "code", "run", "ask", "away", "code", "submit"]


async def test_use_ai_code_adopts_only_a_reply_that_defines_the_entry_point(tmp_path):
    steps = [{"at": 1, "do": "ask", "text": "show me an example please"},
             {"at": 2, "do": "use_ai_code"}, {"at": 3, "do": "submit"}]
    fake, _, logs = await _play(tmp_path, steps)
    snaps = [b for _, p, b, _ in fake.calls if p.endswith("/snapshots")]
    assert snaps == [{"version": 1, "source_code": "def two_sum(nums, target):\n    return [0, 1]"}]
    assert logs[1]["adopted"] is True

    fake, _, logs = await _play(tmp_path / "b", steps, reply="Think about a dict. ```x = 1```")
    assert not [p for _, p, _, _ in fake.calls if p.endswith("/snapshots")]
    assert logs[1] == {"step": 2, "do": "use_ai_code", "adopted": False}


async def test_a_submitted_script_is_not_replayed(tmp_path):
    steps = [{"at": 1, "do": "submit"}]
    await _play(tmp_path, steps)
    fake, _, _ = await _play(tmp_path, steps)
    assert fake.calls == []


async def test_answer_phase_posts_the_saved_questions_with_the_answers(tmp_path):
    await _play(tmp_path, [{"at": 1, "do": "submit"}])
    fake = FakeApi()
    async with httpx.AsyncClient(transport=httpx.MockTransport(fake), base_url="http://api") as client:
        failed = await answer_all(Api(client, _nosleep), State(tmp_path / "state.json"),
                                  {"sim-01": ["Lookups are O(1) in a dict.", "It returns an empty list."]})
    assert failed == []
    post = fake.calls[-1]
    assert post[1] == "/api/attempts/7/explain-back"
    assert post[2] == {"answers": [{"question": "Why a dict?", "answer": "Lookups are O(1) in a dict."},
                                   {"question": "What if empty?", "answer": "It returns an empty list."}]}
    record = State(tmp_path / "state.json").data["sessions"]["sim-01"]
    assert record["status"] == "scored" and record["result"]["tier"] == "Strong"


async def test_answer_phase_skips_a_session_with_the_wrong_number_of_answers(tmp_path):
    await _play(tmp_path, [{"at": 1, "do": "submit"}])
    fake = FakeApi()
    async with httpx.AsyncClient(transport=httpx.MockTransport(fake), base_url="http://api") as client:
        failed = await answer_all(Api(client, _nosleep), State(tmp_path / "state.json"), {"sim-01": ["one"]})
    assert failed == ["sim-01"] and fake.calls == []


async def test_rate_limited_calls_are_retried():
    hits = []

    def handler(request: httpx.Request) -> httpx.Response:
        hits.append(1)
        return httpx.Response(429, headers={"Retry-After": "1"}) if len(hits) < 3 else httpx.Response(200, json={})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://api") as client:
        assert await Api(client, _nosleep).call("POST", "/attempts/1/run") == {}
    assert len(hits) == 3


async def test_profile_mutants_splits_visible_and_hidden(tmp_path):
    from app.features.calibration.simulate import profile_mutants

    (tmp_path / "CP-001.json").write_text((CONTENT_DIR / "CP-001.json").read_text(encoding="utf-8"),
                                          encoding="utf-8")
    rows = (await profile_mutants(tmp_path))["CP-001"]
    assert [r["ref"] for r in rows] == ["starter", "mutant:1", "mutant:2", "mutant:3", "mutant:4"]
    content = load_content_file(CONTENT_DIR / "CP-001.json")
    visible = sum(not t.hidden for t in content.tests)
    assert all(r["visible"].endswith(f"/{visible}") for r in rows)
    # Every mutant is killable, so it fails at least one visible or hidden test.
    for r in rows[1:]:
        passed = sum(int(x.split("/")[0]) for x in (r["visible"], r["hidden"]))
        assert passed < len(content.tests)


def test_helpers():
    assert ai_code("```py\nclass LRUCache:\n    pass\n```", "LRUCache") == "class LRUCache:\n    pass"
    assert ai_code("no code here", "two_sum") is None
    assert chars_added("abc", "abXYc") == 2
    assert chars_added("abc", "abc ") == 1
    assert chars_added("abcdef", "abf") == 1
