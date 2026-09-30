from app.features.feedback.diagnosis import Finding
from app.features.feedback.next_exercise import MAX_CANDIDATES, candidates


async def _catalog(db):
    from app.models import Exercise, User

    user = User(full_name="U", email="u@example.com", password_hash="x")
    rows = [
        ("CP-001", "fresher", "Algorithms", "implement"),
        ("CP-003", "fresher", "Algorithms", "implement"),
        ("CP-004", "fresher", "Debugging", "debug"),
        ("CP-006", "fresher", "Strings", "implement"),
        ("CP-105", "junior", "Algorithms", "implement"),
        ("CP-106", "junior", "Security", "debug"),
        ("CP-202", "senior", "Algorithms", "implement"),
    ]
    exercises = {code: Exercise(code=code, title=code, difficulty="Easy", category=cat, level=level, kind=kind,
                                language="python", summary="s", starter_code="x", hint="", domain_keywords=[])
                 for code, level, cat, kind in rows}
    db.add(user)
    db.add_all(exercises.values())
    await db.flush()
    return user, exercises


def risk(code: str) -> Finding:
    return Finding(code=code, axis="debugging", kind="risk", severity="medium")


async def test_new_student_gets_same_level_first_and_never_two_levels_up(db_session):
    user, ex = await _catalog(db_session)
    out = await candidates(db_session, user.id, ex["CP-001"], [])
    # No ratings yet: the fresher exercises (p = 0.64) are nearest the 0.70 target, then code order.
    assert out == ["CP-003", "CP-004", "CP-006"][:MAX_CANDIDATES]
    assert "CP-202" not in out and "CP-001" not in out


async def test_solved_and_just_started_exercises_are_skipped_or_pushed_down(db_session):
    from app.models import Attempt

    user, ex = await _catalog(db_session)
    db_session.add(Attempt(user_id=user.id, exercise_id=ex["CP-003"].id, status="scored"))
    db_session.add(Attempt(user_id=user.id, exercise_id=ex["CP-006"].id, status="in_progress"))  # started now
    await db_session.flush()
    out = await candidates(db_session, user.id, ex["CP-001"], [])
    assert out == ["CP-004", "CP-105", "CP-106"]


async def test_debugging_risks_prefer_debug_exercises(db_session):
    user, ex = await _catalog(db_session)
    assert (await candidates(db_session, user.id, ex["CP-006"], []))[0] == "CP-001"
    out = await candidates(db_session, user.id, ex["CP-006"], [risk("partial_fix")])
    assert out[0] == "CP-004"


async def test_exercises_for_a_weak_skill_come_first(db_session):
    from app.models import LearnerSkill

    user, ex = await _catalog(db_session)
    ex["CP-006"].skills = ["string-processing"]
    db_session.add_all([LearnerSkill(user_id=user.id, skill="hash-map", rating=1000.0, attempts=2),
                        LearnerSkill(user_id=user.id, skill="graph", rating=1000.0, attempts=2),
                        LearnerSkill(user_id=user.id, skill="string-processing", rating=960.0, attempts=2)])
    await db_session.flush()
    assert (await candidates(db_session, user.id, ex["CP-001"], []))[0] == "CP-006"


async def test_a_senior_exercise_stays_at_senior(db_session):
    user, ex = await _catalog(db_session)
    assert await candidates(db_session, user.id, ex["CP-202"], []) == []
