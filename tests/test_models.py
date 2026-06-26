from app.models import Attempt, Event, Exercise, FluencyReport, User


def test_models_have_tablenames():
    assert User.__tablename__ == "users"
    assert Exercise.__tablename__ == "exercises"
    assert Attempt.__tablename__ == "attempts"
    assert Event.__tablename__ == "events"
    assert FluencyReport.__tablename__ == "fluency_reports"
    # FluencyReport must include the Hypothesis axis (ERD gap fix)
    assert "hypothesis_score" in FluencyReport.__table__.columns
