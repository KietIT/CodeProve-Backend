from app.models import (
    Attempt,
    CodeSnapshot,
    Event,
    Exercise,
    FluencyReport,
    PromptLog,
    TestCase,
    User,
    VerificationAnswer,
)


def test_models_have_tablenames():
    assert User.__tablename__ == "users"
    assert Exercise.__tablename__ == "exercises"
    assert TestCase.__tablename__ == "test_cases"
    assert Attempt.__tablename__ == "attempts"
    assert Event.__tablename__ == "events"
    assert CodeSnapshot.__tablename__ == "code_snapshots"
    assert PromptLog.__tablename__ == "prompt_logs"
    assert VerificationAnswer.__tablename__ == "verification_answers"
    assert FluencyReport.__tablename__ == "fluency_reports"
    # FluencyReport must include the Hypothesis axis (ERD gap fix)
    assert "hypothesis_score" in FluencyReport.__table__.columns


async def test_mutants_and_test_categories_persist(db_session):
    from sqlalchemy import select

    from app.models import Exercise, ExerciseMutant, TestCase

    ex = Exercise(code="CP-990", title="t", difficulty="Easy", category="c", level="fresher",
                  language="python", summary="s", starter_code="x", hint="h", domain_keywords=[])
    db_session.add(ex)
    await db_session.flush()
    db_session.add(TestCase(exercise_id=ex.id, input_data="f(0)", expected_output="0",
                            description="zero", category="boundary", is_hidden=True, order_index=1))
    db_session.add(ExerciseMutant(exercise_id=ex.id, code="def f(n):\n    return 1", bug_line=2,
                                  bug_type="wrong-constant", note_vi="v", note_en="e", order_index=1))
    await db_session.commit()

    tc = (await db_session.execute(select(TestCase))).scalar_one()
    mut = (await db_session.execute(select(ExerciseMutant))).scalar_one()
    assert tc.category == "boundary"
    assert mut.bug_line == 2 and mut.exercise_id == ex.id
