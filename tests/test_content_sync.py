import json

import pytest
from sqlalchemy import select

from app.features.content.sync import sync_content
from tests.test_content_validate import BUGGY_STARTER, _content

pytestmark = pytest.mark.asyncio


async def _exercise(db_session):
    from app.models import Exercise, TestCase

    ex = Exercise(code="CP-004", title="t", difficulty="Easy", category="c", level="fresher", kind="debug",
                  language="python", summary="s", starter_code=BUGGY_STARTER, hint="h", domain_keywords=[])
    db_session.add(ex); await db_session.flush()
    db_session.add(TestCase(exercise_id=ex.id, input_data="sum_to_n(3)", expected_output="6",
                            description="legacy", is_hidden=False, order_index=1))
    await db_session.commit()
    return ex


def _write(tmp_path, review):
    c = _content(review=review)
    raw = json.loads(c.model_dump_json())
    p = tmp_path / "CP-004.json"
    p.write_text(json.dumps(raw), encoding="utf-8")
    return p


APPROVED = {"status": "approved", "author": "claude", "reviewer": "an"}


async def test_dry_run_reports_without_writing(db_session, tmp_path):
    from app.models import TestCase

    await _exercise(db_session)
    results = await sync_content(db_session, [_write(tmp_path, APPROVED)], apply=False)
    assert results[0]["status"] == "ok"
    assert results[0]["hidden"] == 5 and results[0]["mutants"] == 3
    descs = (await db_session.execute(select(TestCase.description))).scalars().all()
    assert descs == ["legacy"]


async def test_apply_replaces_tests_and_mutants(db_session, tmp_path):
    from app.models import Exercise, ExerciseMutant, TestCase

    await _exercise(db_session)
    await sync_content(db_session, [_write(tmp_path, APPROVED)], apply=True)
    await sync_content(db_session, [_write(tmp_path, APPROVED)], apply=True)   # idempotent
    tests = (await db_session.execute(select(TestCase).order_by(TestCase.order_index))).scalars().all()
    assert len(tests) == 7
    assert sum(t.is_hidden for t in tests) == 5
    assert {t.category for t in tests} >= {"happy", "boundary", "edge"}
    assert len((await db_session.execute(select(ExerciseMutant))).scalars().all()) == 3
    ex = (await db_session.execute(select(Exercise))).scalar_one()
    assert ex.reference_solution.startswith("def sum_to_n(n):")


async def test_unapproved_or_self_reviewed_files_are_skipped(db_session, tmp_path):
    await _exercise(db_session)
    draft = await sync_content(db_session, [_write(tmp_path, {"status": "draft", "author": "claude", "reviewer": None})], apply=True)
    assert draft[0]["status"] == "skipped" and "approved" in draft[0]["reason"]
    self_rev = await sync_content(db_session, [_write(tmp_path, {"status": "approved", "author": "an", "reviewer": "an"})], apply=True)
    assert self_rev[0]["status"] == "skipped"


async def test_invalid_content_is_not_written(db_session, tmp_path):
    from app.models import TestCase

    await _exercise(db_session)
    p = _write(tmp_path, APPROVED)
    raw = json.loads(p.read_text(encoding="utf-8"))
    raw["reference_solution"] = "def sum_to_n(n):\n    return 0"
    p.write_text(json.dumps(raw), encoding="utf-8")
    results = await sync_content(db_session, [p], apply=True)
    assert results[0]["status"] == "invalid" and results[0]["errors"]
    assert len((await db_session.execute(select(TestCase))).scalars().all()) == 1


async def test_a_broken_file_is_reported_without_blocking_the_others(db_session, tmp_path):
    await _exercise(db_session)
    good = _write(tmp_path, APPROVED)
    bad = tmp_path / "CP-005.json"
    bad.write_text("{ not json", encoding="utf-8")
    results = await sync_content(db_session, [bad, good], apply=False)
    by_code = {r["code"]: r for r in results}
    assert by_code["CP-005"]["status"] == "invalid"
    assert by_code["CP-004"]["status"] == "ok"


async def test_results_name_the_reviewer_for_the_operator(db_session, tmp_path):
    # The operator running the sync is the real gate, so the dry run shows who
    # approved each file.
    await _exercise(db_session)
    results = await sync_content(db_session, [_write(tmp_path, APPROVED)], apply=False)
    assert results[0]["reviewer"] == "an"


async def test_overrides_are_written_and_reported(db_session, tmp_path):
    from app.models import Exercise

    await _exercise(db_session)
    p = _write(tmp_path, APPROVED)
    raw = json.loads(p.read_text(encoding="utf-8"))
    raw["exercise"] = {"summary": "Sum the integers 1..n (n <= 0 returns 0).",
                       "starter_code": BUGGY_STARTER, "hint": "Try n = 3 by hand."}
    p.write_text(json.dumps(raw), encoding="utf-8")

    dry = await sync_content(db_session, [p], apply=False)
    assert dry[0]["overrides"] == ["summary", "starter_code", "hint"]
    await sync_content(db_session, [p], apply=True)
    ex = (await db_session.execute(select(Exercise))).scalar_one()
    assert ex.summary.startswith("Sum the integers")
    assert ex.hint == "Try n = 3 by hand."


async def test_debug_starter_check_uses_the_override(db_session, tmp_path):
    await _exercise(db_session)
    p = _write(tmp_path, APPROVED)
    raw = json.loads(p.read_text(encoding="utf-8"))
    # An override starter that is already correct leaves no bug to find.
    raw["exercise"] = {"starter_code": raw["reference_solution"]}
    p.write_text(json.dumps(raw), encoding="utf-8")
    results = await sync_content(db_session, [p], apply=False)
    assert results[0]["status"] == "invalid"
    assert any("debug starter passes every test" in e for e in results[0]["errors"])
