"""P2.3 Task 3: at submit, the student's tests are checked against the reference and run on the mutants."""
import pytest
from sqlalchemy import select

REFERENCE = "def add(a, b):\n    return a + b"
MUTANTS = ["def add(a, b):\n    return a - b",               # killed by any ordinary test
           "def add(a, b):\n    return a + b if a else 0",     # killed only by a test with a == 0
           "def add(a, b):\n    return a + b if b != 7 else 0"]  # killed only by a test with b == 7


class NoLLM:
    _model = "fake"

    async def judge(self, system, user, max_tokens=300):
        return {"questions": ["Why?"]}


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    import app.features.attempts.scoring_service as scoring
    monkeypatch.setattr(scoring, "get_mentor_client", lambda: NoLLM())


def t(inp, exp, cat="happy"):
    return {"category": cat, "input": inp, "expected": exp, "why": ""}


async def _attempt(client, db_session, auth_headers, tab=True) -> int:
    from app.models import Exercise, ExerciseMutant, TestCase

    ex = Exercise(code="CP-001", title="Add", difficulty="Easy", category="Algorithms", level="junior",
                  language="python", summary="add", starter_code="def add(a, b):\n    pass", hint="h",
                  domain_keywords=[], reference_solution=REFERENCE, student_tests=tab)
    db_session.add(ex)
    await db_session.flush()
    for i, (cat, hidden) in enumerate([("happy", False), ("boundary", True), ("edge", True)]):
        db_session.add(TestCase(exercise_id=ex.id, input_data="add(1, 2)", expected_output="3",
                                description=f"t{i}", category=cat, is_hidden=hidden, order_index=i))
    for i, code in enumerate(MUTANTS):
        db_session.add(ExerciseMutant(exercise_id=ex.id, code=code, bug_line=2, bug_type=f"bug{i}",
                                      note_vi=f"lỗi {i}", note_en=f"bug {i}", order_index=i))
    await db_session.commit()
    return (await client.post("/api/attempts", json={"exercise_code": "CP-001"}, headers=auth_headers)).json()["attempt_id"]


async def _submit(client, aid, auth_headers, tests=None):
    if tests is not None:
        r = await client.put(f"/api/attempts/{aid}/tests", headers=auth_headers, json={"tests": tests})
        assert r.status_code == 200
    await client.post(f"/api/attempts/{aid}/snapshots", headers=auth_headers,
                      json={"version": 1, "source_code": REFERENCE})
    assert (await client.post(f"/api/attempts/{aid}/submit", headers=auth_headers)).status_code == 200


async def _student_tests(db_session, aid):
    from app.models import Event
    rows = (await db_session.execute(select(Event).where(Event.attempt_id == aid, Event.type == "STUDENT_TESTS")))
    return [r.payload for r in rows.scalars().all()]


async def test_validity_categories_and_killed_mutants_are_recorded_at_submit(client, db_session, auth_headers):
    aid = await _attempt(client, db_session, auth_headers)
    await _submit(client, aid, auth_headers, [
        t("add(1, 2)", "3"),                            # valid, kills mutant 0
        t("add(0, 5)", "5", "boundary"),                # valid, kills mutants 0 and 1
        t("add(1, 1)", "3", "edge"),                    # wrong expected: invalid, not run on mutants
        t("__import__('os')", "0", "error"),            # refused by the allow-list
    ])
    [payload] = await _student_tests(db_session, aid)
    assert [x["valid"] for x in payload["tests"]] == [True, True, False, False]
    assert payload["tests"][3]["reason"].startswith("name '__import__'")
    assert payload["categories"] == ["boundary", "happy"]
    assert payload["exercise_categories"] == ["boundary", "edge", "happy"]
    assert [m["killed"] for m in payload["mutants"]] == [True, True, False]
    assert payload["mutants"][2] == {"id": payload["mutants"][2]["id"], "bug_type": "bug2", "killed": False}
    assert (payload["killed"], payload["total"]) == (2, 3)


async def test_no_tests_is_recorded_too(client, db_session, auth_headers):
    aid = await _attempt(client, db_session, auth_headers)
    await _submit(client, aid, auth_headers)
    [payload] = await _student_tests(db_session, aid)
    assert payload["tests"] == [] and payload["killed"] == 0 and payload["total"] == 3


async def test_exercises_without_the_tab_record_nothing(client, db_session, auth_headers):
    aid = await _attempt(client, db_session, auth_headers, tab=False)
    await _submit(client, aid, auth_headers)
    assert await _student_tests(db_session, aid) == []


async def test_the_report_lists_the_tests_and_what_they_missed(client, db_session, auth_headers, monkeypatch):
    import app.features.attempts.scoring_service as scoring
    from app.core.config import Settings

    class Judge(NoLLM):
        async def judge(self, system, user, max_tokens=300):
            if "explain-back" in system:
                return {"questions": ["Why?"]}
            return {"score": 12, "level": 2, "evidence": "e", "correct": True, "note": "", "items": []}

    monkeypatch.setattr(scoring, "get_mentor_client", lambda: Judge())
    monkeypatch.setattr(scoring, "get_settings", lambda: Settings(scoring_engine="v2"))
    aid = await _attempt(client, db_session, auth_headers)
    await _submit(client, aid, auth_headers, [t("add(1, 2)", "3"), t("add(0, 5)", "5", "boundary")])
    r = await client.post(f"/api/attempts/{aid}/explain-back", headers=auth_headers,
                          json={"answers": [{"question": "Why?", "answer": "because a + b adds the two numbers"}]})
    report = r.json()["feedback"]
    assert report["tests"]["killed"] == 2 and report["tests"]["total"] == 3
    assert report["tests"]["missed"] == ["bug 2"]            # the note, in the report locale (en), never the code
    assert [x["valid"] for x in report["tests"]["tests"]] == [True, True]
    assert report["evidence"]["testing"]["parts"]["mutation"] == 2
    assert "mutants_survived" in [f["code"] for f in report["diagnosis"]["findings"]]
