"""P3.4: next-exercise recommendation from the learner model."""
from datetime import datetime, timedelta, timezone

import pytest

from app.features.learner import elo
from app.features.learner.recommend import TARGET, rank, recommend
from app.models import Attempt, Exercise, LearnerSkill, User


def _ex(id_, code, level="fresher", skills=("hash-map",), kind="implement", difficulty=None) -> Exercise:
    return Exercise(id=id_, code=code, title=code, level=level, kind=kind, skills=list(skills),
                    difficulty_elo=difficulty)


def test_a_new_student_gets_fresher_then_junior_then_senior():
    pool = [_ex(3, "CP-201", "senior"), _ex(2, "CP-101", "junior"), _ex(1, "CP-001", "fresher")]
    out = rank(pool, {}, [], False, set())
    assert [r.code for r in out] == ["CP-001", "CP-101", "CP-201"]
    assert [r.p for r in out] == pytest.approx([0.64, 0.36, 0.151], abs=0.001)


def test_a_strong_student_is_sent_to_the_exercise_near_the_target():
    pool = [_ex(1, "CP-001", "fresher"), _ex(2, "CP-101", "junior"), _ex(3, "CP-201", "senior")]
    out = rank(pool, {"hash-map": 1250.0}, [], False, set())
    assert out[0].code == "CP-101" and out[0].p == pytest.approx(TARGET, abs=0.01)


def test_the_stored_difficulty_replaces_the_level_default():
    easy_junior = _ex(2, "CP-101", "junior", difficulty=900.0)
    out = rank([_ex(1, "CP-001", "fresher", difficulty=1100.0), easy_junior], {}, [], False, set())
    assert out[0].code == "CP-101"


def test_a_weak_skill_wins_at_equal_chance_and_is_reported():
    pool = [_ex(1, "CP-001", skills=("hash-map",)), _ex(2, "CP-002", skills=("graph",))]
    out = rank(pool, {}, ["graph"], False, set())
    assert out[0].code == "CP-002" and out[0].weak_skills == ["graph"] and out[1].weak_skills == []


def test_debug_exercises_get_the_debug_push_only_when_wanted():
    pool = [_ex(1, "CP-001"), _ex(2, "CP-004", kind="debug")]
    assert rank(pool, {}, [], False, set())[0].code == "CP-001"  # tie: code order
    assert rank(pool, {}, [], True, set())[0].code == "CP-004"


def test_a_recent_unfinished_attempt_goes_last():
    pool = [_ex(1, "CP-001"), _ex(2, "CP-003"), _ex(3, "CP-101", "junior")]
    assert [r.code for r in rank(pool, {}, [], False, {1})] == ["CP-003", "CP-101", "CP-001"]


def test_untagged_exercises_rank_by_level_and_ties_are_stable():
    pool = [_ex(2, "CP-003", skills=()), _ex(1, "CP-001", skills=())]
    out = rank(pool, {}, [], False, set(), limit=5)
    assert [r.code for r in out] == ["CP-001", "CP-003"]
    assert out[0].p == pytest.approx(elo.expected(1000, 900), abs=0.001)  # p is rounded to 3 places


async def _setup(db):
    user = User(full_name="An", email="an@student.vn", password_hash="x")
    rows = [("CP-001", "fresher", ["hash-map"], "implement"), ("CP-003", "fresher", ["two-pointers"], "implement"),
            ("CP-004", "fresher", ["control-flow"], "debug"), ("CP-101", "junior", ["hash-map"], "implement"),
            ("CP-201", "senior", ["concurrency"], "implement")]
    exercises = {code: Exercise(code=code, title=code, difficulty="Easy", category="c", level=level, kind=kind,
                                language="python", summary="s", starter_code="", hint="h", domain_keywords=[],
                                skills=skills) for code, level, skills, kind in rows}
    db.add(user); db.add_all(exercises.values())
    await db.flush()
    return user, exercises


async def test_recommend_skips_solved_and_current_and_limits_levels(db_session):
    user, ex = await _setup(db_session)
    db_session.add(Attempt(user_id=user.id, exercise_id=ex["CP-003"].id, status="scored"))
    await db_session.flush()
    out = await recommend(db_session, user.id, current=ex["CP-001"], levels={"fresher", "junior"})
    assert [r.code for r in out] == ["CP-004", "CP-101"]


async def test_recommend_uses_the_weak_skills_and_recent_attempts(db_session):
    user, ex = await _setup(db_session)
    db_session.add_all([LearnerSkill(user_id=user.id, skill="two-pointers", rating=1100.0, attempts=3),
                        LearnerSkill(user_id=user.id, skill="hash-map", rating=1060.0, attempts=3),
                        LearnerSkill(user_id=user.id, skill="control-flow", rating=900.0, attempts=2),
                        LearnerSkill(user_id=user.id, skill="concurrency", rating=500.0, attempts=1)])  # unrated
    now = datetime.now(timezone.utc)
    db_session.add_all([Attempt(user_id=user.id, exercise_id=ex["CP-001"].id, status="in_progress",
                                started_at=now - timedelta(hours=2)),
                        Attempt(user_id=user.id, exercise_id=ex["CP-003"].id, status="in_progress",
                                started_at=now - timedelta(days=3))])  # old: no longer recent
    await db_session.flush()
    out = await recommend(db_session, user.id, limit=5)
    # CP-001 has p = 0.715, closest to the target, but was started 2 h ago and not finished: +0.30.
    # CP-004 (p = 0.50) is pulled up by the weak control-flow skill; concurrency has 1 attempt: not weak.
    assert [r.code for r in out] == ["CP-003", "CP-004", "CP-101", "CP-001", "CP-201"]
    assert {r.code: r.weak_skills for r in out}["CP-004"] == ["control-flow"]
    assert all(r.weak_skills == [] for r in out if r.code != "CP-004")
