"""P2.3 Task 2: save, check (against the reference) and run (on own code) student tests."""
from sqlalchemy import select

REFERENCE = "def add(a, b):\n    return a + b"
T = {"category": "happy", "input": "add(1, 2)", "expected": "3", "why": "basic sum"}


async def _attempt(client, db_session, auth_headers, tab=True, level="junior") -> int:
    from app.models import Exercise

    db_session.add(Exercise(code="CP-001", title="Add", difficulty="Easy", category="Algorithms", level=level,
                            language="python", summary="add two numbers", starter_code="def add(a, b):\n    pass",
                            hint="h", domain_keywords=[], reference_solution=REFERENCE, student_tests=tab))
    await db_session.commit()
    return (await client.post("/api/attempts", json={"exercise_code": "CP-001"}, headers=auth_headers)).json()["attempt_id"]


async def _events(db_session, aid, type_):
    from app.models import Event
    rows = (await db_session.execute(select(Event).where(Event.attempt_id == aid, Event.type == type_)
                                     .order_by(Event.id))).scalars().all()
    return [r.payload for r in rows]


async def _check(client, aid, auth_headers, **test):
    r = await client.post(f"/api/attempts/{aid}/tests/check", headers=auth_headers, json={**T, **test})
    assert r.status_code == 200, r.text
    return r.json()


async def test_tests_are_saved_and_restored(client, db_session, auth_headers):
    aid = await _attempt(client, db_session, auth_headers)
    r = await client.put(f"/api/attempts/{aid}/tests", headers=auth_headers,
                         json={"tests": [T, {**T, "category": "boundary", "input": "add(0, 0)", "expected": "0"}]})
    assert r.status_code == 200
    await client.put(f"/api/attempts/{aid}/tests", headers=auth_headers, json={"tests": [T]})  # latest wins
    state = (await client.get(f"/api/attempts/{aid}", headers=auth_headers)).json()["tests"]
    assert state == {"enabled": True, "required": True, "tests": [T]}
    fresher = await _attempt_other_level(client, db_session, auth_headers)
    assert (await client.get(f"/api/attempts/{fresher}", headers=auth_headers)).json()["tests"]["required"] is False


async def _attempt_other_level(client, db_session, auth_headers) -> int:
    from app.models import Exercise

    db_session.add(Exercise(code="CP-010", title="t", difficulty="Easy", category="Algorithms", level="fresher",
                            language="python", summary="s", starter_code="x", hint="h", domain_keywords=[],
                            reference_solution=REFERENCE, student_tests=True))
    await db_session.commit()
    return (await client.post("/api/attempts", json={"exercise_code": "CP-010"}, headers=auth_headers)).json()["attempt_id"]


async def test_saving_is_limited_and_validated(client, db_session, auth_headers):
    aid = await _attempt(client, db_session, auth_headers)
    too_many = await client.put(f"/api/attempts/{aid}/tests", headers=auth_headers, json={"tests": [T] * 11})
    assert too_many.status_code == 422
    bad_category = await client.put(f"/api/attempts/{aid}/tests", headers=auth_headers,
                                    json={"tests": [{**T, "category": "weird"}]})
    assert bad_category.status_code == 422


async def test_the_check_says_valid_or_wrong_but_never_the_reference_output(client, db_session, auth_headers):
    aid = await _attempt(client, db_session, auth_headers)
    assert await _check(client, aid, auth_headers) == {"status": "valid", "reason": None}
    wrong = await _check(client, aid, auth_headers, expected="4")
    assert wrong == {"status": "wrong_expected", "reason": None}  # no "3" anywhere
    # Expected values are compared as Python values: [1,2] and [1, 2] are the same.
    assert (await _check(client, aid, auth_headers, input="add([1], [2])", expected="[1,2]"))["status"] == "valid"
    assert [p["status"] for p in await _events(db_session, aid, "TEST_CHECK")] == ["valid", "wrong_expected", "valid"]


async def test_the_check_refuses_unsafe_inputs_and_hides_error_details(client, db_session, auth_headers):
    aid = await _attempt(client, db_session, auth_headers)
    unsafe = await _check(client, aid, auth_headers, input="__import__('os').getcwd()")
    assert unsafe["status"] == "error" and "__import__" in unsafe["reason"]
    crash = await _check(client, aid, auth_headers, input="add(1)")
    assert crash == {"status": "error", "reason": "TypeError"}  # the type only, not the reference's message


async def test_run_executes_the_saved_tests_on_the_students_own_code(client, db_session, auth_headers):
    aid = await _attempt(client, db_session, auth_headers)
    await client.put(f"/api/attempts/{aid}/tests", headers=auth_headers,
                     json={"tests": [T, {**T, "input": "globals()", "expected": "{}"}]})
    r = await client.post(f"/api/attempts/{aid}/tests/run", headers=auth_headers,
                          json={"source_code": "def add(a, b):\n    return a - b"})
    assert r.status_code == 200
    first, second = r.json()["results"]
    assert first == {"passed": False, "actual": "-1", "error": None}   # their own code: actual values are fine
    assert second["passed"] is False and "globals" in second["error"]   # same rules as at submit


async def test_exercises_without_the_tab_have_no_tests(client, db_session, auth_headers):
    off = await _attempt(client, db_session, auth_headers, tab=False)
    assert (await client.put(f"/api/attempts/{off}/tests", headers=auth_headers, json={"tests": [T]})).status_code == 400
    assert (await client.post(f"/api/attempts/{off}/tests/check", headers=auth_headers, json=T)).status_code == 400
    assert (await client.get(f"/api/attempts/{off}", headers=auth_headers)).json()["tests"] is None


async def test_submitted_attempts_are_read_only(client, db_session, auth_headers):
    from app.models import Attempt

    aid = await _attempt(client, db_session, auth_headers)
    attempt = (await db_session.execute(select(Attempt).where(Attempt.id == aid))).scalar_one()
    attempt.status = "submitted"
    await db_session.commit()
    assert (await client.put(f"/api/attempts/{aid}/tests", headers=auth_headers, json={"tests": [T]})).status_code == 409
    r = await client.post(f"/api/attempts/{aid}/tests/check", headers=auth_headers, json=T)
    assert r.status_code == 409
