import pytest
from sqlalchemy import select

pytestmark = pytest.mark.asyncio


async def _attempt(client, db_session, auth_headers) -> int:
    from app.models import Exercise, TestCase

    ex = Exercise(code="CP-950", title="Double", difficulty="Easy", category="Algorithms",
                  level="fresher", language="python", summary="double x", kind="implement",
                  starter_code="def double(x):\n    return x * 2", hint="", domain_keywords=[])
    db_session.add(ex)
    await db_session.flush()
    db_session.add(TestCase(exercise_id=ex.id, input_data="double(2)", expected_output="4",
                            description="t1", is_hidden=False, order_index=1))
    db_session.add(TestCase(exercise_id=ex.id, input_data="double(0)", expected_output="0",
                            description="t2", is_hidden=False, order_index=2))
    await db_session.commit()
    r = await client.post("/api/attempts", json={"exercise_code": "CP-950"}, headers=auth_headers)
    return r.json()["attempt_id"]


async def _run_events(db_session, aid):
    from app.models import Event

    rows = (await db_session.execute(
        select(Event).where(Event.attempt_id == aid, Event.type == "RUN").order_by(Event.id)
    )).scalars().all()
    return [r.payload for r in rows]


async def test_run_records_starter_flag_and_pass_ratio(client, db_session, auth_headers):
    aid = await _attempt(client, db_session, auth_headers)
    # 1) untouched starter (the scaffold the student sees is "def double(x):\n    pass")
    await client.post(f"/api/attempts/{aid}/run", headers=auth_headers,
                      json={"source_code": "def double(x):\n    pass\n", "run_tests": True})
    # 2) half-right code: passes double(0) only
    await client.post(f"/api/attempts/{aid}/run", headers=auth_headers,
                      json={"source_code": "def double(x):\n    return x * 3", "run_tests": True})
    # 3) correct
    await client.post(f"/api/attempts/{aid}/run", headers=auth_headers,
                      json={"source_code": "def double(x):\n    return x + x", "run_tests": True})

    payloads = await _run_events(db_session, aid)
    assert [p["isStarter"] for p in payloads] == [True, False, False]
    assert [p["passRatio"] for p in payloads] == [0.0, 0.5, 1.0]
    assert [p["passed"] for p in payloads] == [False, False, True]


async def test_run_executes_visible_tests_only(client, db_session, auth_headers):
    from app.models import TestCase

    aid = await _attempt(client, db_session, auth_headers)   # 2 visible cases
    ex_id = (await db_session.execute(select(TestCase.exercise_id))).scalars().first()
    db_session.add(TestCase(exercise_id=ex_id, input_data="double(-1)", expected_output="-2",
                            description="secret_negative", is_hidden=True, order_index=3))
    await db_session.commit()

    r = await client.post(f"/api/attempts/{aid}/run", headers=auth_headers,
                          json={"source_code": "def double(x):\n    return x + x", "run_tests": True})
    body = r.json()
    assert body["total"] == 2
    assert all(c["name"] != "secret_negative" for c in body["cases"])
