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
