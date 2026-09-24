import pytest
from sqlalchemy import select

import app.features.attempts.scoring_service as scoring_service
import app.features.mentor.client as client_mod

pytestmark = pytest.mark.asyncio

PARTLY_RIGHT = "def inc(x):\n    return abs(x) + 1"   # passes inc(1) and inc(0), fails inc(-5)


class FakeClient:
    _model = "fake"

    async def chat(self, *a, **k):
        return {"text": "", "prompt_tokens": 0, "completion_tokens": 0, "code_loc": 0}

    async def judge(self, system, user, max_tokens=300):
        if "questions" in system:
            return {"questions": ["Why does your function add one?"]}
        return {"score": 16, "reason": "solid"}


@pytest.fixture(autouse=True)
def _patch(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(client_mod, "get_mentor_client", lambda: fake)
    monkeypatch.setattr(scoring_service, "get_mentor_client", lambda: fake)


async def _attempt(client, db_session, auth_headers, code: str | None = PARTLY_RIGHT) -> int:
    from app.models import Exercise, TestCase

    ex = Exercise(code="CP-960", title="Increment", difficulty="Easy", category="Algorithms", level="fresher",
                  language="python", summary="Return x + 1.", kind="implement",
                  starter_code="def inc(x):\n    return x + 1", hint="", domain_keywords=[])
    db_session.add(ex)
    await db_session.flush()
    for i, (inp, exp, cat, hidden) in enumerate([("inc(1)", "2", "happy", False),
                                                  ("inc(0)", "1", "boundary", True),
                                                  ("inc(-5)", "-4", "edge", True)], start=1):
        db_session.add(TestCase(exercise_id=ex.id, input_data=inp, expected_output=exp, description=f"case {i}",
                                category=cat, is_hidden=hidden, order_index=i))
    await db_session.commit()
    aid = (await client.post("/api/attempts", json={"exercise_code": "CP-960"}, headers=auth_headers)).json()["attempt_id"]
    if code is not None:
        await client.post(f"/api/attempts/{aid}/snapshots", headers=auth_headers,
                          json={"version": 1, "source_code": code})
    return aid


async def _submit_event(db_session, aid):
    from app.models import Event

    return (await db_session.execute(
        select(Event).where(Event.attempt_id == aid, Event.type == "SUBMIT_TESTS")
    )).scalar_one().payload


async def test_submit_runs_every_test_and_reveals_only_counts(client, db_session, auth_headers):
    aid = await _attempt(client, db_session, auth_headers)
    r = await client.post(f"/api/attempts/{aid}/submit", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["tests"] == {"passed": 2, "total": 3, "hidden_passed": 1, "hidden_total": 2,
                                 "failed_categories": ["edge"]}
    assert "inc(-5)" not in r.text   # hidden inputs never reach the student at submit

    payload = await _submit_event(db_session, aid)
    assert payload["passRatio"] == round(2 / 3, 3)
    assert payload["failures"] == [{"description": "case 3", "category": "edge", "hidden": True,
                                    "input": "inc(-5)", "expected": "-4", "actual": "6", "error": None}]


async def test_submit_without_any_code_fails_every_test(client, db_session, auth_headers):
    aid = await _attempt(client, db_session, auth_headers, code=None)
    r = await client.post(f"/api/attempts/{aid}/submit", headers=auth_headers)
    assert r.json()["tests"]["passed"] == 0


async def test_submitting_a_scored_attempt_is_rejected(client, db_session, auth_headers):
    from app.models import Attempt

    aid = await _attempt(client, db_session, auth_headers)
    attempt = (await db_session.execute(select(Attempt).where(Attempt.id == aid))).scalar_one()
    attempt.status = "scored"
    await db_session.commit()
    r = await client.post(f"/api/attempts/{aid}/submit", headers=auth_headers)
    assert r.status_code == 409


async def test_report_lists_the_failing_hidden_test_and_scores_testing_from_it(client, db_session, auth_headers):
    aid = await _attempt(client, db_session, auth_headers)
    questions = (await client.post(f"/api/attempts/{aid}/submit", headers=auth_headers)).json()["questions"]
    eb = await client.post(f"/api/attempts/{aid}/explain-back", headers=auth_headers,
                           json={"answers": [{"question": questions[0], "answer": "It returns x plus one for every input."}]})
    body = eb.json()
    assert body["axes"]["testing"] == round(20 * 2 / 3, 2)
    suite = body["feedback"]["submit_tests"]
    assert (suite["passed"], suite["total"], suite["failed_categories"]) == (2, 3, ["edge"])
    assert suite["failures"][0]["input"] == "inc(-5)"
    implementation = next(t for t in body["timeline"] if t["key"] == "implementation")
    assert implementation["coverage_pct"] == 66

    report = (await client.get(f"/api/attempts/{aid}/report", headers=auth_headers)).json()
    assert report["feedback"]["submit_tests"] == suite
