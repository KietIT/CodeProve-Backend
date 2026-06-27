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
    assert body["rubric"][0] == ["Understanding", "25%"]
    assert "test_basic" in body["tests"]
