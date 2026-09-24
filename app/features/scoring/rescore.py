"""Recompute stored fluency reports with the current scoring engine.

    python -m app.features.scoring.rescore          # dry run: print old -> new
    python -m app.features.scoring.rescore --apply  # write the new scores

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
        changes.append({"attempt_id": attempt.id, "exercise": exercise.code,
                        "old": report.overall_score, "new": result["overall"]})
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


async def _main(apply: bool) -> None:
    async with async_session_maker() as db:
        changes = await rescore_all(db, apply)
    for c in changes:
        print(f"attempt {c['attempt_id']:>6}  {c['exercise']:<8}  {c['old']:6.2f} -> {c['new']:6.2f}")
    verb = "rescored" if apply else "would rescore (dry run, use --apply to write)"
    print(f"{len(changes)} report(s) {verb}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="write the new scores (default: dry run)")
    asyncio.run(_main(parser.parse_args().apply))
