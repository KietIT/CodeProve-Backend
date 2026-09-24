import pytest
from sqlalchemy import select

from app.features.scoring.rescore import rescore_all

pytestmark = pytest.mark.asyncio


async def _legacy_report(db_session):
    """A first-try solve scored by the old engine (debugging 0, no prompt)."""
    from app.models import Attempt, Event, Exercise, FluencyReport, User

    user = User(full_name="U", email="u@example.com", password_hash="x")
    ex = Exercise(code="CP-001", title="t", difficulty="Easy", category="c", level="fresher",
                  language="python", summary="s", starter_code="x", hint="h", domain_keywords=[])
    db_session.add_all([user, ex]); await db_session.flush()
    at = Attempt(user_id=user.id, exercise_id=ex.id, score=53.45, status="scored", integrity_status="green")
    db_session.add(at); await db_session.flush()
    for t, ts, p in [("OPEN", 0, {"problemReadRatio": 1.0}),
                     ("HYPOTHESIS", 30000, {"proposedBy": "user", "correct": True}),
                     ("CODE_EDIT", 60000, {"charsAdded": 200}),
                     ("RUN", 90000, {"passed": True}),
                     ("SUBMIT", 95000, {})]:
        db_session.add(Event(attempt_id=at.id, type=t, ts=ts, payload=p, integrity_flags=[]))
    db_session.add(FluencyReport(attempt_id=at.id, understanding_score=18.2, hypothesis_score=17,
                                 prompt_score=0, verification_score=8, testing_score=12,
                                 debugging_score=0, explanation_score=18, overall_score=53.45, feedback={}))
    await db_session.commit()
    return at.id


async def test_dry_run_reports_changes_without_writing(db_session):
    from app.models import FluencyReport

    aid = await _legacy_report(db_session)
    changes = await rescore_all(db_session, apply=False)
    assert len(changes) == 1
    assert changes[0]["attempt_id"] == aid
    assert changes[0]["old"] == 53.45
    assert changes[0]["new"] > 85
    rep = (await db_session.execute(select(FluencyReport))).scalar_one()
    assert rep.overall_score == 53.45        # untouched


async def test_apply_rewrites_report_and_attempt(db_session):
    from app.models import Attempt, FluencyReport

    await _legacy_report(db_session)
    changes = await rescore_all(db_session, apply=True)
    rep = (await db_session.execute(select(FluencyReport))).scalar_one()
    at = (await db_session.execute(select(Attempt))).scalar_one()
    assert rep.overall_score == changes[0]["new"]
    assert at.score == changes[0]["new"]
    assert rep.debugging_score is None
    assert rep.prompt_score is None
    assert rep.explanation_score == 18            # the LLM judgement is reused, not re-asked
    assert rep.feedback["rescored_from"]["overall"] == 53.45
    assert rep.feedback["not_applicable"]["debugging"] == "no_failure"
    assert len(rep.feedback["timeline"]) == 3


async def test_changes_carry_per_axis_old_and_new(db_session):
    await _legacy_report(db_session)
    change = (await rescore_all(db_session, apply=False))[0]
    assert change["axes_old"]["debugging"] == 0
    assert change["axes_new"]["debugging"] is None
    assert change["axes_new"]["testing"] == 20.0
    assert change["explanation"] == 18
