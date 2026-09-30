"""P3.3: the learner profile (axes, recurring issues) and the deterministic learner brief."""
from datetime import datetime, timedelta, timezone

import pytest

from app.features.feedback.templates import TEMPLATES
from app.features.learner.brief import learner_brief
from app.features.learner.profile import LearnerProfile, RecurringIssue, SkillRating, profile
from app.features.content.skills import TAXONOMY
from app.models import Attempt, Exercise, FluencyReport, LearnerSkill, User

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)
NO_AXES = dict.fromkeys(("understanding", "hypothesis", "prompting", "verification", "testing", "debugging"))


def _skill(key: str, rating: float, attempts: int = 3) -> SkillRating:
    return SkillRating(key=key, rating=rating, attempts=attempts, **TAXONOMY[key])


def _profile(**over) -> LearnerProfile:
    base = dict(scored_attempts=6, skills=[], axes=NO_AXES, recurring=[], window=5)
    return LearnerProfile(**{**base, **over})


def test_no_scored_attempt_gives_one_neutral_line():
    assert learner_brief(_profile(scored_attempts=0), "vi") == "Chưa có bài nào được chấm."
    assert learner_brief(_profile(scored_attempts=0), "en") == "No scored exercise yet."


def test_skills_below_two_attempts_are_never_named():
    brief = learner_brief(_profile(skills=[_skill("graph", 1200, attempts=1), _skill("hash-map", 800, attempts=1)]))
    assert "Đồ thị" not in brief and "Bảng băm" not in brief
    assert "Chưa đủ dữ liệu" in brief


def test_strongest_and_weakest_skills_with_a_plain_word():
    skills = [_skill("hash-map", 1120), _skill("recursion", 1010), _skill("graph", 990), _skill("concurrency", 900)]
    brief = learner_brief(_profile(skills=skills), "vi")
    assert "Kỹ năng mạnh: Bảng băm (dict) (1120, tốt); Đệ quy (1010, trung bình)." in brief
    assert "Kỹ năng cần luyện: Đồng thời, đa luồng (900, cần luyện); Đồ thị (990, trung bình)." in brief


def test_a_skill_is_never_both_strong_and_weak():
    brief = learner_brief(_profile(skills=[_skill("hash-map", 1100), _skill("graph", 950)]), "en")
    assert "Strongest skills: Hash map (1100, good); Graphs (950, average)." in brief
    assert "Skills to practise" not in brief


def test_axes_line_names_the_best_and_worst_axis():
    axes = {**NO_AXES, "understanding": 2.6, "testing": 0.8, "prompting": 2.0}
    assert "trục mạnh nhất là Thấu hiểu (2.6/3), yếu nhất là Testing (0.8/3)" in learner_brief(_profile(axes=axes))
    flat = {**NO_AXES, "understanding": 2.0, "testing": 2.0}
    assert "trục" not in learner_brief(_profile(axes=flat))  # nothing to say when every axis is equal


def test_recurring_issues_use_the_reviewed_practice_phrase():
    code = next(iter(TEMPLATES))
    brief = learner_brief(_profile(recurring=[RecurringIssue(code=code, count=3)]), "en")
    assert f"{TEMPLATES[code]['en']['practice']} (3/5)" in brief


def test_the_brief_stays_short_in_the_worst_case():
    skills = [_skill(k, 1000 + i) for i, k in enumerate(TAXONOMY)]
    longest = sorted(TEMPLATES, key=lambda c: -len(TEMPLATES[c]["vi"]["practice"]))[:5]
    p = _profile(skills=skills, axes={**NO_AXES, "understanding": 3.0, "testing": 0.0},
                 recurring=[RecurringIssue(code=c, count=5) for c in longest])
    for locale in ("vi", "en"):
        brief = learner_brief(p, locale)
        assert len(brief) < 1200 and brief.count("\n") == 4  # 5 lines, about 300 tokens at most


async def _report(db, user, ex, minutes, levels=None, risks=(), overall=50.0):
    a = Attempt(user_id=user.id, exercise_id=ex.id, status="scored", submitted_at=T0 + timedelta(minutes=minutes))
    db.add(a); await db.flush()
    feedback = {} if levels is None else {"engine": "v2", "levels": levels, "diagnosis": {"findings": [
        {"code": c, "kind": "risk"} for c in risks] + [{"code": "strong_tests", "kind": "strength"}]}}
    db.add(FluencyReport(attempt_id=a.id, understanding_score=0, hypothesis_score=0, explanation_score=0,
                         overall_score=overall, feedback=feedback))


async def test_profile_reads_skills_and_the_last_five_v2_reports(db_session):
    u = User(full_name="An", email="an@student.vn", password_hash="x")
    other = User(full_name="B", email="b@student.vn", password_hash="x")
    ex = Exercise(code="CP-001", title="t", difficulty="Easy", category="c", level="fresher", language="python",
                  summary="s", starter_code="", hint="h", domain_keywords=[])
    db_session.add_all([u, other, ex]); await db_session.flush()
    db_session.add_all([LearnerSkill(user_id=u.id, skill="graph", rating=980.0, attempts=2),
                        LearnerSkill(user_id=u.id, skill="hash-map", rating=1040.04, attempts=3),
                        LearnerSkill(user_id=u.id, skill="retired-skill", rating=1500.0, attempts=9),
                        LearnerSkill(user_id=other.id, skill="graph", rating=1300.0, attempts=5)])
    await _report(db_session, u, ex, 0, {**NO_AXES, "testing": 3}, risks=["no_student_tests"])  # 6th newest: out
    await _report(db_session, u, ex, 1)  # v1 report: counted, but has no levels
    for i, testing in enumerate([0, 1, 2, 1, None]):
        await _report(db_session, u, ex, 10 + i, {**NO_AXES, "understanding": 2, "testing": testing},
                      risks=["no_student_tests", "invalid_tests"][: 2 if i < 2 else 1])
    await _report(db_session, other, ex, 20, {**NO_AXES, "testing": 3}, risks=["invalid_tests"])
    await db_session.commit()

    p = await profile(db_session, u.id)
    assert p.scored_attempts == 7 and p.window == 5
    assert [(s.key, s.rating, s.attempts) for s in p.skills] == [("hash-map", 1040.0, 3), ("graph", 980.0, 2)]
    assert p.axes["understanding"] == 2 and p.axes["testing"] == 1.0 and p.axes["debugging"] is None
    assert p.recurring == [RecurringIssue(code="no_student_tests", count=5), RecurringIssue(code="invalid_tests", count=2)]


async def test_profile_of_a_new_student_is_empty(db_session):
    u = User(full_name="An", email="an@student.vn", password_hash="x")
    db_session.add(u); await db_session.commit()
    p = await profile(db_session, u.id)
    assert (p.scored_attempts, p.skills, p.recurring, p.window) == (0, [], [], 0)
    assert set(p.axes.values()) == {None}


def test_the_brief_contains_no_personal_data():
    p = _profile(skills=[_skill("hash-map", 1100)])
    for locale in ("vi", "en"):
        brief = learner_brief(p, locale)
        assert "@" not in brief and "```" not in brief
