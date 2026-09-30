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


async def test_radar_axis_is_null_when_never_observed(client, db_session, auth_headers):
    from app.models import Attempt, Exercise, FluencyReport, User
    from sqlalchemy import select
    user = (await db_session.execute(select(User))).scalars().first()
    ex = Exercise(code="CP-001", title="Two-Sum", difficulty="Easy", category="Algorithms",
                  level="fresher", language="python", acceptance=1, summary="s", starter_code="x",
                  hint="h", domain_keywords=["a"])
    db_session.add(ex); await db_session.flush()
    at = Attempt(user_id=user.id, exercise_id=ex.id, score=90.0, status="scored", integrity_status="green")
    db_session.add(at); await db_session.flush()
    db_session.add(FluencyReport(attempt_id=at.id, understanding_score=18, hypothesis_score=17,
                                 prompt_score=None, verification_score=None, testing_score=20,
                                 debugging_score=None, explanation_score=18, overall_score=90.0, feedback={}))
    await db_session.commit()

    radar = {r["name"]: r["value"] for r in (await client.get("/api/dashboard", headers=auth_headers)).json()["radar"]}
    assert radar["Prompting"] is None
    assert radar["Debugging"] is None
    assert radar["Testing"] == 100.0


async def test_dashboard_recommends_unsolved_exercises_nearest_the_target(client, db_session, auth_headers):
    from sqlalchemy import select

    from app.models import Attempt, Exercise, LearnerSkill, User

    assert (await client.get("/api/dashboard", headers=auth_headers)).json()["recommended"] == []  # no exercises

    user = (await db_session.execute(select(User))).scalars().first()
    rows = [("CP-001", "fresher", ["hash-map"]), ("CP-003", "fresher", ["two-pointers"]),
            ("CP-004", "fresher", ["control-flow"]), ("CP-006", "fresher", ["hash-map", "string-processing"]),
            ("CP-101", "junior", ["hash-map"]), ("CP-201", "senior", ["concurrency"])]
    exercises = {code: Exercise(code=code, title=code, difficulty="Easy", category="c", level=level,
                                language="python", summary="s", starter_code="x", hint="h", domain_keywords=[],
                                skills=skills) for code, level, skills in rows}
    db_session.add_all(exercises.values()); await db_session.flush()
    db_session.add(Attempt(user_id=user.id, exercise_id=exercises["CP-001"].id, status="scored", score=70.0))
    db_session.add_all([LearnerSkill(user_id=user.id, skill="two-pointers", rating=1000.0, attempts=2),
                        LearnerSkill(user_id=user.id, skill="control-flow", rating=1000.0, attempts=2),
                        LearnerSkill(user_id=user.id, skill="string-processing", rating=960.0, attempts=2)])
    await db_session.commit()

    body = (await client.get("/api/dashboard", headers=auth_headers)).json()
    assert [r["code"] for r in body["recommended"]] == ["CP-006", "CP-003", "CP-004"]  # CP-001 is solved
    first = body["recommended"][0]
    assert first == {"code": "CP-006", "title": "CP-006", "level": "fresher", "kind": "implement",
                     "skills": [{"key": "hash-map", "vi": "Bảng băm (dict)", "en": "Hash map"},
                                {"key": "string-processing", "vi": "Xử lý chuỗi", "en": "String processing"}],
                     "reason_skills": ["string-processing"]}
    assert "p" not in first  # the success chance is never sent
