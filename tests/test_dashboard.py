import pytest

pytestmark = pytest.mark.asyncio


async def test_dashboard_empty_then_populated(client, db_session, auth_headers):
    empty = await client.get("/api/dashboard", headers=auth_headers)
    assert empty.status_code == 200
    assert empty.json()["kpis"]["completed"] == 0

    # seed a scored attempt directly
    from app.models import Attempt, Exercise, FluencyReport, User
    from sqlalchemy import select
    user = (await db_session.execute(select(User))).scalars().first()
    ex = Exercise(code="CP-001", title="Two-Sum", difficulty="Easy", category="Algorithms",
                  level="fresher", language="python", acceptance=1, summary="s", starter_code="x",
                  hint="h", domain_keywords=["a"])
    db_session.add(ex); await db_session.flush()
    at = Attempt(user_id=user.id, exercise_id=ex.id, score=84.0, status="scored", integrity_status="green")
    db_session.add(at); await db_session.flush()
    db_session.add(FluencyReport(attempt_id=at.id, understanding_score=17, hypothesis_score=15,
                                 prompt_score=16, verification_score=14, testing_score=12,
                                 debugging_score=13, explanation_score=18, overall_score=84.0, feedback={}))
    await db_session.commit()

    full = await client.get("/api/dashboard", headers=auth_headers)
    body = full.json()
    assert body["kpis"]["completed"] == 1
    assert round(body["kpis"]["avg_score"], 1) == 84.0
    assert len(body["radar"]) == 6
    assert body["recent"][0]["title"] == "Two-Sum"
    assert body["recent"][0]["ok"] is True            # 84 >= 50
    assert body["trend"] == [84.0]
    # radar value = axis score * 5; understanding 17 -> 85
    radar = {r["name"]: r["value"] for r in body["radar"]}
    assert radar["Understanding"] == 85.0
    assert radar["Testing"] == 60.0                    # nullable axis present (12 * 5)
