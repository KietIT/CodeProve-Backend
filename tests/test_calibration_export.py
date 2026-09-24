import json
import re

from app.features.calibration.export import build_sessions, scrub


async def _user(db, email="alice@example.com", name="Alice Nguyen"):
    from app.models import User

    user = User(full_name=name, email=email, password_hash="x")
    db.add(user)
    await db.flush()
    return user


async def _exercise(db):
    from app.models import Exercise

    ex = Exercise(code="CP-001", title="Two-Sum", difficulty="Easy", category="c", level="fresher",
                  kind="implement", language="python", summary="Return the two indices.",
                  starter_code="def f(): pass", hint="", domain_keywords=[])
    db.add(ex)
    await db.flush()
    return ex


async def _session(db, user, ex, *, answered=True, overall=62.5):
    from app.models import (Attempt, CodeSnapshot, Event, FluencyReport, PromptLog,
                            VerificationAnswer)

    at = Attempt(user_id=user.id, exercise_id=ex.id, status="scored", score=overall)
    db.add(at)
    await db.flush()
    base = 1_700_000_000_000
    for t, dt, payload in [
        ("OPEN", 0, {}),
        ("HYPOTHESIS", 60_000, {"proposedBy": "user", "correct": True,
                                "text": "hash map; mail me at alice@example.com"}),
        ("PROMPT", 120_000, {"messageText": "x"}),
        ("AI_REPLY", 121_000, {"injectedError": True, "aiCode": [{"loc": 3}]}),
        ("RUN", 180_000, {"passed": False, "passRatio": 0.5, "isStarter": False}),
        ("SUBMIT_TESTS", 300_000, {"passRatio": 0.75, "passed": 6, "total": 8, "hiddenPassed": 4,
                                   "hiddenTotal": 6, "failedCategories": ["edge"], "failures": []}),
        ("TAB_HIDDEN", 310_000, {}),
    ]:
        db.add(Event(attempt_id=at.id, type=t, ts=base + dt, payload=payload, integrity_flags=[]))
    db.add(PromptLog(attempt_id=at.id, prompt="I am Alice, call me on 0912345678", response="Think about a dict."))
    db.add(CodeSnapshot(attempt_id=at.id, version=1, source_code="def two_sum(n, t):\n    return [0, 1]"))
    if answered:
        db.add(VerificationAnswer(attempt_id=at.id, question="Why a dict?", answer="Lookups are O(1).", score=14))
    db.add(FluencyReport(attempt_id=at.id, understanding_score=12, hypothesis_score=17, prompt_score=10,
                         verification_score=None, testing_score=15, debugging_score=None,
                         explanation_score=14, overall_score=overall, feedback={}))
    await db.commit()
    return at


async def test_sessions_are_anonymised_and_engine_scores_kept_apart(db_session):
    user, ex = await _user(db_session), await _exercise(db_session)
    await _session(db_session, user, ex)
    sessions, engine = await build_sessions(db_session, salt="fixed")

    assert len(sessions) == 1
    s = sessions[0]
    dumped = json.dumps(sessions, ensure_ascii=False)
    for secret in ("alice@example.com", "Alice Nguyen", "0912345678", "1700000"):
        assert secret not in dumped
    assert "user_id" not in dumped and "overall" not in dumped
    assert re.fullmatch(r"S[0-9a-f]{8}", s["id"])

    assert s["exercise"]["code"] == "CP-001"
    assert s["hypotheses"][0]["text"] == "hash map; mail me at [email]"
    assert s["prompts"][0]["prompt"] == "I am Alice, call me on [số điện thoại]"
    assert s["prompts"][0]["planted_bug"] is True
    assert s["runs"] == [{"at_min": 3.0, "pass_ratio": 0.5, "starter": False}]
    assert s["submit_tests"]["hidden_total"] == 6
    assert s["final_code"].startswith("def two_sum")
    assert s["explain_back"] == [{"question": "Why a dict?", "answer": "Lookups are O(1)."}]
    assert s["integrity"]["tab_hidden"] == 1
    assert engine[s["id"]]["overall"] == 62.5
    assert engine[s["id"]]["axes"]["verification"] is None


async def test_ids_are_stable_for_one_salt_and_unlinkable_across_salts(db_session):
    user, ex = await _user(db_session), await _exercise(db_session)
    await _session(db_session, user, ex)
    a, _ = await build_sessions(db_session, salt="one")
    b, _ = await build_sessions(db_session, salt="one")
    c, _ = await build_sessions(db_session, salt="two")
    assert a[0]["id"] == b[0]["id"] != c[0]["id"]


async def test_per_user_cap_and_unanswered_sessions_are_skipped(db_session):
    ex = await _exercise(db_session)
    heavy = await _user(db_session)
    other = await _user(db_session, email="bob@example.com", name="Bob")
    for _ in range(4):
        await _session(db_session, heavy, ex)
    await _session(db_session, other, ex, answered=False)   # no explain-back: not ratable
    sessions, _ = await build_sessions(db_session, per_user=3, salt="s")
    assert len(sessions) == 3


def test_scrub_removes_emails_and_vietnamese_phone_numbers():
    assert scrub("x@y.com và +84912345678, 0987654321") == "[email] và [số điện thoại], [số điện thoại]"
    assert scrub(None) == ""
