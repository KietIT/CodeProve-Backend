import pytest

pytestmark = pytest.mark.asyncio


async def _seed_one(db_session):
    from app.models import Exercise, TestCase
    ex = Exercise(code="CP-001", title="Two-Sum", difficulty="Easy", category="Algorithms",
                  level="fresher", language="python", acceptance=57.7, summary="...",
                  starter_code="def f(): pass", hint="think", domain_keywords=["algorithms"])
    db_session.add(ex)
    await db_session.flush()
    db_session.add(TestCase(exercise_id=ex.id, description="test_basic", is_hidden=False, order_index=1))
    await db_session.commit()


async def test_list_and_detail(client, db_session, auth_headers):
    await _seed_one(db_session)
    lst = await client.get("/api/exercises", headers=auth_headers)
    assert lst.status_code == 200
    groups = lst.json()
    assert any(g["level"] == "fresher" for g in groups)

    detail = await client.get("/api/exercises/CP-001", headers=auth_headers)
    assert detail.status_code == 200
    body = detail.json()
    assert body["code"] == "CP-001"
    assert body["num"] == 1
    assert body["rubric"][0] == ["Understanding", "25%"]
    assert "test_basic" in body["tests"]

    fresher = next(g for g in groups if g["level"] == "fresher")
    assert fresher["exercises"][0]["num"] == 1


async def test_detail_starter_stripped_for_implement_kept_for_debug(client, db_session, auth_headers):
    from app.models import Exercise

    impl_code = "def solve(x):\n    return x * 2"
    buggy_code = "def sum_to_n(n):\n    total = 0\n    for i in range(1, n):   # bug\n        total += i\n    return total"
    db_session.add(Exercise(code="CP-901", title="Implement It", difficulty="Easy", category="Algorithms",
                            level="fresher", language="python", summary="...", kind="implement",
                            starter_code=impl_code, hint="", domain_keywords=[]))
    db_session.add(Exercise(code="CP-902", title="Fix the Bug", difficulty="Easy", category="Debugging",
                            level="fresher", language="python", summary="...", kind="debug",
                            starter_code=buggy_code, hint="", domain_keywords=[]))
    await db_session.commit()

    impl = (await client.get("/api/exercises/CP-901", headers=auth_headers)).json()
    assert impl["kind"] == "implement"
    assert "return x * 2" not in impl["starter"]  # body stripped to a stub
    assert "pass" in impl["starter"]

    debug = (await client.get("/api/exercises/CP-902", headers=auth_headers)).json()
    assert debug["kind"] == "debug"
    assert debug["starter"] == buggy_code  # buggy body shown verbatim
