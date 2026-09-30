"""Load reviewed exercise content into the database.

    python -m app.features.content.sync              # dry run, every file
    python -m app.features.content.sync CP-004 ...   # dry run, some files
    python -m app.features.content.sync --apply      # write

Only files approved by a reviewer other than the author, and that pass the
sandbox validator, are written. A written exercise has its test cases and
mutants replaced by the file's (the file is the source of truth).
"""
import argparse
import asyncio
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import async_session_maker
from app.features.content.schema import CONTENT_DIR, ExerciseContent, load_content_file
from app.features.content.validate import validate_content
from app.features.exercises.debug_regions import derive
from app.features.exercises.starters import student_starter
from app.features.student_tests.safety import ENABLE_SHARE, enabled_share
from app.models import Exercise, ExerciseMutant, TestCase


async def _write(db: AsyncSession, ex: Exercise, content: ExerciseContent) -> None:
    ex.reference_solution = content.reference_solution
    if content.exercise:
        for field in content.exercise.fields_set():
            setattr(ex, field, getattr(content.exercise, field))
    await db.execute(delete(TestCase).where(TestCase.exercise_id == ex.id))
    await db.execute(delete(ExerciseMutant).where(ExerciseMutant.exercise_id == ex.id))
    for i, t in enumerate(content.tests, start=1):
        db.add(TestCase(exercise_id=ex.id, input_data=t.input, expected_output=t.expected,
                        description=t.description, category=t.category, is_hidden=t.hidden,
                        order_index=i, weight=1.0))
    for i, m in enumerate(content.mutants, start=1):
        db.add(ExerciseMutant(exercise_id=ex.id, code=m.code, bug_line=m.bug_line, bug_type=m.bug_type,
                              note_vi=m.note_vi, note_en=m.note_en, order_index=i))
    if content.debug and content.debug.review.approved:
        # A draft block leaves the stored metadata as it is.
        ex.debug_meta = debug_meta(content, ex.starter_code)
    ex.student_tests = enabled_share(content) >= ENABLE_SHARE


def debug_meta(content: ExerciseContent, current_starter: str) -> dict:
    """The stored form of an approved debug block: regions resolved on the served starter."""
    served = student_starter(content.starter_for(current_starter), "debug")
    d = content.debug
    return {"regions": d.regions or derive(served, content.reference_solution),
            "explanation_vi": d.explanation_vi, "explanation_en": d.explanation_en,
            "hint_vi": d.hint_vi, "hint_en": d.hint_en}


def _debug_status(content: ExerciseContent) -> str | None:
    if content.debug is None:
        return None
    return "approved" if content.debug.review.approved else "draft"


async def sync_content(db: AsyncSession, files: list[Path], apply: bool) -> list[dict]:
    results: list[dict] = []
    for path in sorted(files):
        try:
            content = load_content_file(path)
        except ValueError as exc:  # bad JSON or schema (pydantic's ValidationError is a ValueError)
            # One broken file must not block the others.
            results.append({"code": path.stem, "status": "invalid", "errors": [str(exc)]})
            continue
        ex = (await db.execute(select(Exercise).where(Exercise.code == content.code))).scalar_one_or_none()
        if ex is None:
            results.append({"code": content.code, "status": "skipped", "reason": "exercise not in the database"})
            continue
        if not content.is_approved:
            results.append({"code": content.code, "status": "skipped",
                            "reason": "not approved by a reviewer other than the author"})
            continue
        errors = await validate_content(content, ex.kind, content.starter_for(ex.starter_code))
        if errors:
            results.append({"code": content.code, "status": "invalid", "errors": errors})
            continue
        results.append({"code": content.code, "status": "ok", "tests": len(content.tests),
                        "hidden": sum(t.hidden for t in content.tests), "mutants": len(content.mutants),
                        "reviewer": content.review.reviewer,
                        "overrides": content.exercise.fields_set() if content.exercise else [],
                        "debug": _debug_status(content),
                        "student_tests": round(enabled_share(content), 2),
                        "debug_reviewer": content.debug.review.reviewer if content.debug else None})
        if apply:
            await _write(db, ex, content)
    if apply:
        await db.commit()
    return results


async def _main(codes: list[str], apply: bool) -> int:
    files = [CONTENT_DIR / f"{c.upper()}.json" for c in codes] if codes else sorted(CONTENT_DIR.glob("*.json"))
    missing = [f for f in files if not f.exists()]
    for f in missing:
        print(f"{f.stem}  MISSING  no content file at {f}")
    files = [f for f in files if f.exists()]
    async with async_session_maker() as db:
        results = await sync_content(db, files, apply)
    for r in results:
        if r["status"] == "ok":
            print(f"{r['code']}  ok       tests={r['tests']} hidden={r['hidden']} mutants={r['mutants']}"
                  f"  reviewer={r['reviewer']}")
            if r["overrides"]:
                # Student-facing text/code changes: make them impossible to miss in the dry run.
                print(f"    ! overrides the exercise's {', '.join(r['overrides'])}")
            tab = "on" if r["student_tests"] >= ENABLE_SHARE else "off"
            print(f"    tests tab {tab} ({r['student_tests']:.0%} of its tests fit the student-test rules)")
            if r["debug"] == "approved":
                print(f"    debug block approved by {r['debug_reviewer']}: bug regions, explanation and hint written")
            elif r["debug"] == "draft":
                print("    debug block is a draft: not written")
        elif r["status"] == "skipped":
            print(f"{r['code']}  skipped  {r['reason']}")
        else:
            print(f"{r['code']}  INVALID")
            for e in r["errors"]:
                print(f"    - {e}")
    written = sum(r["status"] == "ok" for r in results)
    print(f"{written} exercise(s) {'written' if apply else 'ready (dry run, use --apply to write)'}")
    return 1 if missing or any(r["status"] == "invalid" for r in results) else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("codes", nargs="*", help="exercise codes (default: every content file)")
    parser.add_argument("--apply", action="store_true", help="write to the database (default: dry run)")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_main(args.codes, args.apply)))
