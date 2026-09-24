"""Recompute stored fluency reports with the current scoring engine.

    python -m app.features.scoring.rescore          # dry run: print old -> new
    python -m app.features.scoring.rescore --apply  # write the new scores
    add --details to print every axis (old -> new, "NA" = not applicable)

Scores are rebuilt from each attempt's stored events and its stored
explain-back score (the LLM is not called again). Each rewritten report keeps
its previous overall under feedback["rescored_from"].
"""
import argparse
import asyncio
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import async_session_maker
from app.features.attempts.scoring_service import _events_as_dicts, integrity_from_features, report_columns
from app.features.scoring.engine import score_attempt
from app.models import Attempt, Exercise, FluencyReport

# Engine axis -> FluencyReport column.
_AXIS_COLUMNS = {
    "understanding": "understanding_score",
    "hypothesis": "hypothesis_score",
    "prompting": "prompt_score",
    "verification": "verification_score",
    "testing": "testing_score",
    "debugging": "debugging_score",
}


async def rescore_all(db: AsyncSession, apply: bool) -> list[dict]:
    rows = (await db.execute(
        select(FluencyReport, Attempt, Exercise)
        .join(Attempt, Attempt.id == FluencyReport.attempt_id)
        .join(Exercise, Exercise.id == Attempt.exercise_id)
        .order_by(FluencyReport.id)
    )).all()
    changes: list[dict] = []
    for report, attempt, exercise in rows:
        events = await _events_as_dicts(db, attempt.id)
        result = score_attempt(events, explain_score=report.explanation_score, exercise_kind=exercise.kind)
        changes.append({
            "attempt_id": attempt.id, "exercise": exercise.code, "kind": exercise.kind,
            "explanation": report.explanation_score,
            "old": report.overall_score, "new": result["overall"],
            "axes_old": {a: getattr(report, col) for a, col in _AXIS_COLUMNS.items()},
            "axes_new": dict(result["axes"]),
        })
        if not apply:
            continue
        previous = report.overall_score
        for column, value in report_columns(result).items():
            setattr(report, column, value)
        report.feedback = {**report.feedback, "rescored_from": {
            "overall": previous, "at": datetime.now(timezone.utc).isoformat()}}
        attempt.score = result["overall"]
        attempt.integrity_status = integrity_from_features(result["features"])
    if apply:
        await db.commit()
    return changes


def _fmt(v: float | None) -> str:
    return "  NA" if v is None else f"{v:4.1f}"


async def _main(apply: bool, details: bool) -> None:
    async with async_session_maker() as db:
        changes = await rescore_all(db, apply)
    for c in changes:
        print(f"attempt {c['attempt_id']:>6}  {c['exercise']:<8}  {c['old']:6.2f} -> {c['new']:6.2f}")
        if details:
            print(f"    kind={c['kind']}  explain-back={c['explanation']:.1f}/20")
            for axis in _AXIS_COLUMNS:
                print(f"    {axis:<13} {_fmt(c['axes_old'][axis])} -> {_fmt(c['axes_new'][axis])}")
    verb = "rescored" if apply else "would rescore (dry run, use --apply to write)"
    print(f"{len(changes)} report(s) {verb}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="write the new scores (default: dry run)")
    parser.add_argument("--details", action="store_true", help="print every axis, old -> new")
    args = parser.parse_args()
    asyncio.run(_main(args.apply, args.details))
