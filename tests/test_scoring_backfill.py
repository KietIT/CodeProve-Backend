import json

from sqlalchemy import select

from app.features.scoring.backfill import backfill_judges
from app.features.scoring.rescore import rescore_all


class FakeJudge:
    _model = "fake"

    def __init__(self):
        self.calls = 0

    async def judge(self, system, user, max_tokens=300):
        self.calls += 1
        if "rate each message" in system:
            return {"prompts": [{"i": 1, "level": 3, "evidence": "what I tried"}]}
        if "hypothesis" in system:
            return {"correct": True, "note": "ok", "level": 3, "evidence": "dict, O(n)"}
        return {"score": 15, "level": 3, "evidence": "because"}


async def _scored_attempt(db, email="a@example.com"):
    """A pre-P1.4 session: judged by v1 only (no levels anywhere)."""
    from app.models import Attempt, Event, Exercise, FluencyReport, PromptLog, User, VerificationAnswer

    user = User(full_name="U", email=email, password_hash="x")
    ex = (await db.execute(select(Exercise))).scalars().first()
    if ex is None:
        ex = Exercise(code="CP-001", title="t", difficulty="Easy", category="c", level="fresher", language="python",
                      summary="Two-sum", starter_code="x", hint="h", domain_keywords=[])
        db.add(ex)
    db.add(user)
    await db.flush()
    at = Attempt(user_id=user.id, exercise_id=ex.id, status="scored", score=50)
    db.add(at)
    await db.flush()
    for t, minute, p in [("OPEN", 0, {}),
                         ("HYPOTHESIS", 1, {"proposedBy": "user", "correct": True, "text": "dict, O(n)"}),
                         ("CODE_EDIT", 2, {"charsAdded": 50}),
                         ("PROMPT", 3, {"messageText": "I tried X", "messageLength": 9}),
                         ("AI_REPLY", 3.1, {"aiCode": []}),
                         ("RUN", 4, {"passed": True, "passRatio": 1.0, "isStarter": False}),
                         ("SUBMIT", 5, {}),
                         ("SUBMIT_TESTS", 5, {"passed": 8, "total": 8, "visiblePassed": 2, "visibleTotal": 2})]:
        db.add(Event(attempt_id=at.id, type=t, ts=int(minute * 60_000), payload=p, integrity_flags=[]))
    db.add_all([PromptLog(attempt_id=at.id, prompt="I tried X", response="Look at Y."),
                VerificationAnswer(attempt_id=at.id, question="Why?", answer="Because lookups are O(1) here.",
                                   score=15),
                FluencyReport(attempt_id=at.id, understanding_score=14, hypothesis_score=17, prompt_score=10,
                              verification_score=None, testing_score=20, debugging_score=None,
                              explanation_score=15, overall_score=50, feedback={})])
    await db.commit()
    return at


async def test_backfill_asks_once_per_missing_verdict_and_is_idempotent(db_session):
    from app.models import Event

    at = await _scored_attempt(db_session)
    fake = FakeJudge()
    assert await backfill_judges(db_session, at, fake) == 3        # explain, prompts, hypothesis
    await db_session.commit()
    assert await backfill_judges(db_session, at, fake) == 0        # nothing left to ask
    judged = [e.payload for e in (await db_session.execute(
        select(Event).where(Event.attempt_id == at.id, Event.type == "JUDGE"))).scalars()]
    kinds = sorted(p["kind"] for p in judged)
    assert kinds == ["explain", "hypothesis", "prompts"]
    hyp = next(p for p in judged if p["kind"] == "hypothesis")
    assert hyp["for_ts"] == 60_000 and hyp["level"] == 3
    assert fake.calls == 3


async def test_rescore_v2_on_the_golden_set_writes_engine_json(db_session, tmp_path):
    from app.models import FluencyReport

    golden = await _scored_attempt(db_session)
    await _scored_attempt(db_session, email="b@example.com")      # not in the golden set
    keys = {"S1": golden.id}
    changes = await rescore_all(db_session, apply=False, engine="v2", attempt_ids=set(keys.values()),
                                client=FakeJudge())
    assert [c["attempt_id"] for c in changes] == [golden.id]
    change = changes[0]
    assert change["levels"]["hypothesis"] == 3 and change["levels"]["understanding"] == 3
    assert change["levels"]["prompting"] == 3
    # Dry run: the stored report is untouched (the new verdicts are kept for later runs).
    rep = (await db_session.execute(select(FluencyReport).where(FluencyReport.attempt_id == golden.id))).scalar_one()
    assert rep.overall_score == 50

    from app.features.scoring.rescore import engine_json
    out = engine_json(changes, keys)
    assert out == {"S1": {"overall": change["new"], "axes": change["axes_new"], "levels": change["levels"]}}
    json.dumps(out)
