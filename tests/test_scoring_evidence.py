from datetime import datetime, timedelta, timezone

from app.features.scoring.evidence import adopted, code_blocks, load_evidence

BASE = datetime(2026, 9, 26, 10, 0, tzinfo=timezone.utc)
BASE_MS = int(BASE.timestamp() * 1000)


def ms(minutes: float) -> int:
    return BASE_MS + int(minutes * 60_000)


def at(minutes: float) -> datetime:
    return BASE + timedelta(minutes=minutes)


async def _attempt(db, kind: str = "implement"):
    from app.models import Attempt, Exercise, User

    user = User(full_name="Sim", email="sim@example.com", password_hash="x")
    ex = Exercise(code="CP-001", title="Two-Sum", difficulty="Easy", category="c", level="fresher", kind=kind,
                  language="python", summary="Return the two indices.", starter_code="def two_sum(nums, target):\n    pass",
                  hint="", domain_keywords=[])
    db.add_all([user, ex])
    await db.flush()
    attempt = Attempt(user_id=user.id, exercise_id=ex.id, status="scored")
    db.add(attempt)
    await db.flush()
    return attempt


async def test_load_evidence_collects_everything_in_time_order(db_session):
    from app.models import CodeSnapshot, Event, PromptLog, VerificationAnswer

    attempt = await _attempt(db_session, kind="debug")
    for type_, minute, payload in [
        ("SUBMIT_TESTS", 9, {"passed": 7, "total": 8}),
        ("OPEN", 0, {}),
        ("AI_REPLY", 3.01, {"injectedError": True, "aiCode": [{"loc": 3}]}),
        ("AI_REPLY", 5.01, {"injectedError": False, "aiCode": []}),
        ("RUN", 4, {"passed": False, "passRatio": 0.5, "isStarter": False}),
        ("JUDGE", 9.5, {"kind": "explain", "levels": [2, 3]}),
        ("JUDGE", 2, {"kind": "hypothesis", "level": 3}),
        ("SUBMIT_TESTS", 8, {"passed": 5, "total": 8}),
    ]:
        db_session.add(Event(attempt_id=attempt.id, type=type_, ts=ms(minute), payload=payload, integrity_flags=[]))
    db_session.add_all([
        PromptLog(attempt_id=attempt.id, prompt="why?", response="Try:\n```python\nx = 1\n```", created_at=at(3)),
        PromptLog(attempt_id=attempt.id, prompt="thanks", response="Good luck", created_at=at(5)),
        CodeSnapshot(attempt_id=attempt.id, version=2, source_code="second", created_at=at(4)),
        CodeSnapshot(attempt_id=attempt.id, version=1, source_code="first", created_at=at(2)),
        VerificationAnswer(attempt_id=attempt.id, question="Why?", answer="Because.", score=10),
    ])
    await db_session.commit()

    ev = await load_evidence(db_session, attempt)

    assert ev.exercise_kind == "debug"
    assert [e["type"] for e in ev.events][:2] == ["OPEN", "JUDGE"]
    assert [(r.prompt, r.injected, r.at_ms) for r in ev.replies] == [("why?", True, ms(3)), ("thanks", False, ms(5))]
    assert ev.replies[0].blocks == ["x = 1"]
    assert [s.code for s in ev.snapshots] == ["first", "second"]
    assert ev.final_code == "second"
    assert ev.code_at(ms(3)) == "first" and ev.code_at(ms(1)) is None
    assert ev.submit_suite == {"passed": 7, "total": 8}  # the last one wins
    assert [r["passRatio"] for r in ev.runs_after(ms(3))] == [0.5]
    assert ev.judges["hypothesis"] == [{"kind": "hypothesis", "level": 3}]
    assert ev.judges["explain"][0]["levels"] == [2, 3]
    assert ev.answers == [{"question": "Why?", "answer": "Because."}]


async def test_evidence_without_prompts_or_snapshots(db_session):
    attempt = await _attempt(db_session)
    ev = await load_evidence(db_session, attempt)
    assert ev.replies == [] and ev.snapshots == [] and ev.final_code == ""
    assert ev.submit_suite is None and ev.judges == {}


def test_code_blocks_keep_fenced_code_only():
    reply = "Look:\n```python\ndef f():\n    return 1\n```\nand ```js\nx()\n``` then `inline`."
    assert code_blocks(reply) == ["def f():\n    return 1", "x()"]
    assert code_blocks("") == [] and code_blocks(None) == []


def test_adopted_is_the_share_of_block_lines_found_in_the_code():
    block = "def f(a):\n    total = 0\n    for x in a:\n        total += x\n    return total"
    assert adopted(block, block) == 1.0
    assert adopted(block, "def f(a):\n  return sum(a)") == 0.2  # only the signature line survives
    # Indentation and blank lines do not matter; comments are not code.
    assert adopted("x = 1\n\n# note\ny = 2", "  x = 1\n  y = 2\n") == 1.0
    assert adopted("", "x = 1") == 0.0
