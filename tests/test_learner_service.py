"""P3.3: the learner model is updated after scoring and can be rebuilt from reports."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.features.learner import elo
from app.features.learner.service import rebuild, record_attempt, replay
from app.models import Attempt, Exercise, FluencyReport, LearnerSkill, User

pytestmark = pytest.mark.asyncio
T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


async def _user(db, email="an@student.vn") -> User:
    u = User(full_name="x", email=email, password_hash="x")
    db.add(u); await db.flush()
    return u


async def _exercise(db, code="CP-001", level="fresher", skills=("hash-map", "two-pointers")) -> Exercise:
    ex = Exercise(code=code, title="t", difficulty="Easy", category="c", level=level, language="python",
                  summary="s", starter_code="", hint="h", domain_keywords=[], skills=list(skills))
    db.add(ex); await db.flush()
    return ex


async def _score(db, user, ex, overall, minutes) -> Attempt:
    """What score_with_explanations does: store the report, update the model, mark scored."""
    a = Attempt(user_id=user.id, exercise_id=ex.id, status="submitted", submitted_at=T0 + timedelta(minutes=minutes))
    db.add(a); await db.flush()
    db.add(FluencyReport(attempt_id=a.id, understanding_score=0, hypothesis_score=0, explanation_score=0,
                         overall_score=overall, feedback={}))
    await record_attempt(db, a, ex, overall)
    a.status, a.score = "scored", overall
    await db.commit()
    return a


async def _ratings(db) -> dict[tuple[int, str], tuple[float, int]]:
    rows = (await db.execute(select(LearnerSkill))).scalars().all()
    return {(r.user_id, r.skill): (r.rating, r.attempts) for r in rows}


def _same(a: dict, b: dict) -> bool:
    return a.keys() == b.keys() and all(a[k][1] == b[k][1] and a[k][0] == pytest.approx(b[k][0]) for k in a)


async def test_a_scored_attempt_rates_every_tag_and_the_exercise(db_session):
    u, ex = await _user(db_session), await _exercise(db_session)
    await _score(db_session, u, ex, 90, 0)
    gain = elo.K_STUDENT * (0.9 - elo.expected(1000, 900))
    assert await _ratings(db_session) == {(u.id, "hash-map"): (pytest.approx(1000 + gain), 1),
                                          (u.id, "two-pointers"): (pytest.approx(1000 + gain), 1)}
    assert ex.difficulty_elo == pytest.approx(900 - elo.K_EXERCISE * (0.9 - elo.expected(1000, 900)))


async def test_a_repeat_moves_the_student_but_not_the_difficulty(db_session):
    u, ex = await _user(db_session), await _exercise(db_session)
    await _score(db_session, u, ex, 90, 0)
    after_first = ex.difficulty_elo
    await _score(db_session, u, ex, 95, 10)
    assert ex.difficulty_elo == after_first
    rating, attempts = (await _ratings(db_session))[(u.id, "hash-map")]
    assert attempts == 2 and rating > 1000 + elo.K_STUDENT * (0.9 - elo.expected(1000, 900))


async def test_sim_accounts_do_not_move_the_difficulty(db_session):
    sim, ex = await _user(db_session, "calib.sim07@example.com"), await _exercise(db_session)
    await _score(db_session, sim, ex, 10, 0)
    assert ex.difficulty_elo is None
    assert (await _ratings(db_session))[(sim.id, "hash-map")][0] < 1000


async def test_an_untagged_exercise_changes_nothing(db_session):
    u, ex = await _user(db_session), await _exercise(db_session, skills=())
    await _score(db_session, u, ex, 90, 0)
    assert await _ratings(db_session) == {} and ex.difficulty_elo is None


async def test_rebuild_matches_the_incremental_model_and_is_idempotent(db_session):
    an, binh = await _user(db_session), await _user(db_session, "binh@student.vn")
    sim = await _user(db_session, "calib.sim01@example.com")
    easy, hard = await _exercise(db_session), await _exercise(db_session, "CP-201", "senior", ("concurrency",))
    for i, (user, ex, overall) in enumerate([(an, easy, 80), (binh, easy, 40), (an, hard, 55), (an, easy, 95),
                                             (sim, hard, 20), (binh, hard, 70), (sim, easy, 100)]):
        await _score(db_session, user, ex, overall, i)
    incremental = await _ratings(db_session)
    difficulties = {easy.id: easy.difficulty_elo, hard.id: hard.difficulty_elo}

    dry = await rebuild(db_session, apply=False)
    assert dry.reports == 7 and dry.students == 3
    assert _same(dry.ratings, incremental)
    assert dry.difficulties == pytest.approx(difficulties)

    for _ in range(2):  # applying twice gives the same model
        await rebuild(db_session, apply=True)
        assert _same(await _ratings(db_session), incremental)
        await db_session.refresh(easy); await db_session.refresh(hard)
        assert {easy.id: easy.difficulty_elo, hard.id: hard.difficulty_elo} == pytest.approx(difficulties)


async def test_rebuild_follows_submit_time_not_insert_order(db_session):
    u, ex = await _user(db_session), await _exercise(db_session)
    late = await _score(db_session, u, ex, 30, 50)
    await _score(db_session, u, ex, 90, 0)  # submitted earlier, stored later
    result = await replay(db_session)
    first_move = 900 - elo.K_EXERCISE * (0.9 - elo.expected(1000, 900))
    assert result.difficulties[ex.id] == pytest.approx(first_move)  # the 90 was the first attempt
    assert late.id < max(a.id for a in (await db_session.execute(select(Attempt))).scalars())


async def _scored_via_api(client, db_session, auth_headers, monkeypatch):
    import app.features.attempts.scoring_service as scoring
    from tests.test_debug_locate import JudgeClient, _attempt, _submit_and_explain

    monkeypatch.setattr(scoring, "get_mentor_client", lambda: JudgeClient())
    aid = await _attempt(client, db_session, auth_headers)
    ex = (await db_session.execute(select(Exercise))).scalar_one()
    ex.skills = ["control-flow"]
    await db_session.commit()
    return await _submit_and_explain(client, aid, auth_headers)


async def test_explain_back_updates_the_learner_model(client, db_session, auth_headers, monkeypatch):
    report = await _scored_via_api(client, db_session, auth_headers, monkeypatch)
    [row] = (await db_session.execute(select(LearnerSkill))).scalars().all()
    assert row.skill == "control-flow" and row.attempts == 1
    expected = 1000 + elo.K_STUDENT * (elo.outcome(report["overall"]) - elo.expected(1000, 900))
    assert row.rating == pytest.approx(expected)


async def test_a_learner_model_error_never_fails_scoring(client, db_session, auth_headers, monkeypatch, caplog):
    import app.features.attempts.scoring_service as scoring

    async def broken(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(scoring, "record_attempt", broken)
    report = await _scored_via_api(client, db_session, auth_headers, monkeypatch)
    assert "overall" in report
    assert (await db_session.execute(select(Attempt))).scalar_one().status == "scored"
    assert "learner model update failed" in caplog.text
