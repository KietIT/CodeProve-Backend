"""P3.6: every LLM call's token usage is logged to llm_calls (never the text)."""
import json

import pytest
from sqlalchemy import select

import app.features.mentor.client as client_mod
import app.features.mentor.service as service_mod
from app.features.mentor import prompts, usage
from app.features.mentor.usage import judge_kind, llm_scope, record
from app.models import Exercise, LlmCall, User


@pytest.mark.parametrize("system,kind", [
    (prompts.EXPLAIN_QUESTION_SYSTEM + "\nIMPORTANT: Write the questions in Vietnamese.", "explain_questions"),
    (prompts.EXPLAIN_SCORE_SYSTEM, "explain"), (prompts.HYPOTHESIS_JUDGE_SYSTEM, "hypothesis"),
    (prompts.LOCATE_JUDGE_SYSTEM, "locate"), (prompts.PROMPT_JUDGE_SYSTEM, "prompts"),
    (prompts.DAILY_CHALLENGE_SYSTEM, "daily"), (prompts.FEEDBACK_WRITER_SYSTEM, "feedback"),
    ("something else", "other"),
])
def test_judge_kind_follows_the_system_prompt(system, kind):
    assert judge_kind(system) == kind


def test_the_table_holds_no_text():
    assert set(LlmCall.__table__.columns.keys()) == {
        "id", "kind", "model", "prompt_tokens", "cached_tokens", "completion_tokens", "user_id", "attempt_id",
        "created_at"}


async def test_record_only_inside_a_scope_and_never_raises(db_session, monkeypatch, caplog):
    record("ciel", "m", 10, 0, 5)  # no scope: nothing to do
    assert len(db_session.new) == 0
    with llm_scope(db_session, None, None):
        record("explain", "m", 10, 4, 5)
    [row] = list(db_session.new)
    assert (row.kind, row.prompt_tokens, row.cached_tokens, row.completion_tokens) == ("explain", 10, 4, 5)

    def broken(**kw):
        raise RuntimeError("boom")

    monkeypatch.setattr(usage, "LlmCall", broken)
    with llm_scope(db_session):
        record("ciel", "m", 1, 0, 1)
    assert "could not log an LLM call" in caplog.text


class _FakeOpenAI:
    """Stands in for AsyncOpenAI: Ciel gets text, judges get JSON; fixed usage."""

    def __init__(self):
        outer = self

        class Completions:
            async def create(self, **kw):
                json_mode = "response_format" in kw
                content = json.dumps({"correct": True, "note": "ok", "level": 2, "evidence": "e"}) if json_mode \
                    else "a hint"
                usage_ = type("U", (), {"prompt_tokens": 1500, "completion_tokens": 40,
                                        "prompt_tokens_details": type("D", (), {"cached_tokens": 1024})()})()
                msg = type("M", (), {"content": content})()
                return type("R", (), {"choices": [type("C", (), {"message": msg})()], "usage": usage_})()

        self.chat = type("Chat", (), {"completions": Completions()})()


@pytest.fixture
def real_client(monkeypatch):
    mc = client_mod.MentorClient.__new__(client_mod.MentorClient)
    mc._client, mc._model = _FakeOpenAI(), "gpt-4o-mini"
    monkeypatch.setattr(client_mod, "_singleton", mc)
    return mc


async def _attempt(client, db_session, auth_headers) -> int:
    db_session.add(Exercise(code="CP-001", title="t", difficulty="Easy", category="c", level="junior",
                            language="python", summary="s", starter_code="x", hint="h", domain_keywords=[]))
    await db_session.commit()
    return (await client.post("/api/attempts", json={"exercise_code": "CP-001"}, headers=auth_headers)).json()["attempt_id"]


async def _calls(db_session):
    return (await db_session.execute(select(LlmCall).order_by(LlmCall.id))).scalars().all()


async def test_a_ciel_message_logs_one_call_with_its_usage(client, db_session, auth_headers, real_client):
    aid = await _attempt(client, db_session, auth_headers)
    r = await client.post(f"/api/attempts/{aid}/mentor", json={"message": "hint?"}, headers=auth_headers)
    assert r.status_code == 200
    [call] = await _calls(db_session)
    user_id = (await db_session.execute(select(User.id))).scalar_one()
    assert (call.kind, call.model, call.prompt_tokens, call.cached_tokens, call.completion_tokens) == \
        ("ciel", "gpt-4o-mini", 1500, 1024, 40)
    assert (call.user_id, call.attempt_id) == (user_id, aid)


async def test_a_guard_retry_logs_a_second_call(client, db_session, auth_headers, real_client, monkeypatch):
    seen = []

    async def solves_first(db, exercise_id, text):
        seen.append(text)
        return len(seen) == 1

    monkeypatch.setattr(service_mod.guard, "solves_exercise", solves_first)
    aid = await _attempt(client, db_session, auth_headers)
    await client.post(f"/api/attempts/{aid}/mentor", json={"message": "hint?"}, headers=auth_headers)
    assert [c.kind for c in await _calls(db_session)] == ["ciel", "ciel_retry"]


async def test_judges_are_logged_too(client, db_session, auth_headers, real_client):
    aid = await _attempt(client, db_session, auth_headers)
    r = await client.post(f"/api/attempts/{aid}/hypothesis", json={"text": "use a dict"}, headers=auth_headers)
    assert r.status_code == 200
    assert [(c.kind, c.attempt_id) for c in await _calls(db_session)] == [("hypothesis", aid)]


async def test_a_logging_failure_does_not_fail_the_request(client, db_session, auth_headers, real_client,
                                                           monkeypatch):
    def broken(**kw):
        raise RuntimeError("boom")

    monkeypatch.setattr(usage, "LlmCall", broken)
    aid = await _attempt(client, db_session, auth_headers)
    r = await client.post(f"/api/attempts/{aid}/mentor", json={"message": "hint?"}, headers=auth_headers)
    assert r.status_code == 200 and r.json()["reply"] == "a hint"
