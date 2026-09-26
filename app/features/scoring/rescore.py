"""Recompute stored fluency reports with the current scoring engine.

    python -m app.features.scoring.rescore          # dry run: print old -> new
    python -m app.features.scoring.rescore --apply  # write the new scores
    add --details to print every axis (old -> new, "NA" = not applicable)

Engine v2 (P1.4):
    python -m app.features.scoring.rescore --engine v2 --backfill-judges \\
        --keys keys.json --out engine_v2.json       # golden set only, dry run

Scores are rebuilt from each attempt's stored events and its stored
explain-back score. v1 never calls the LLM. v2 reads the rubric verdicts
stored as events; --backfill-judges asks the judges once for verdicts an
attempt is missing and stores them (new events only), so the next run reuses
them. Each rewritten report keeps its previous overall under
feedback["rescored_from"].
"""
import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import async_session_maker
from app.features.attempts.scoring_service import _events_as_dicts, integrity_from_features, report_columns
from app.features.scoring.backfill import backfill_judges
from app.features.scoring.engine import score_attempt
from app.features.scoring.engine_v2 import score_attempt_v2
from app.features.scoring.evidence import load_evidence
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


async def rescore_all(db: AsyncSession, apply: bool, engine: str = "v1", attempt_ids: set[int] | None = None,
                      client=None) -> list[dict]:
    """Rescore every report (or only `attempt_ids`). With engine v2 and a judge
    `client`, missing rubric verdicts are asked for and stored first."""
    query = (select(FluencyReport, Attempt, Exercise)
             .join(Attempt, Attempt.id == FluencyReport.attempt_id)
             .join(Exercise, Exercise.id == Attempt.exercise_id)
             .order_by(FluencyReport.id))
    if attempt_ids is not None:
        query = query.where(Attempt.id.in_(attempt_ids))
    rows = (await db.execute(query)).all()
    changes: list[dict] = []
    for report, attempt, exercise in rows:
        if engine == "v2":
            if client is not None:
                await backfill_judges(db, attempt, client)
                await db.commit()  # keep the verdicts even on a dry run: they are paid for
            result = score_attempt_v2(await load_evidence(db, attempt), report.explanation_score)
        else:
            events = await _events_as_dicts(db, attempt.id)
            result = score_attempt(events, explain_score=report.explanation_score, exercise_kind=exercise.kind)
        changes.append({
            "attempt_id": attempt.id, "exercise": exercise.code, "kind": exercise.kind,
            "explanation": report.explanation_score,
            "old": report.overall_score, "new": result["overall"],
            "axes_old": {a: getattr(report, col) for a, col in _AXIS_COLUMNS.items()},
            "axes_new": dict(result["axes"]),
            "levels": result.get("levels"),
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


def engine_json(changes: list[dict], keys: dict[str, int]) -> dict:
    """Changes in the export's engine.json shape, keyed by golden-set session id."""
    by_attempt = {c["attempt_id"]: c for c in changes}
    return {sid: {"overall": by_attempt[aid]["new"], "axes": by_attempt[aid]["axes_new"],
                  "levels": by_attempt[aid]["levels"]}
            for sid, aid in keys.items() if aid in by_attempt}


def _fmt(v: float | None) -> str:
    return "  NA" if v is None else f"{v:4.1f}"


async def _main(apply: bool, details: bool, engine: str, keys_path: Path | None, out: Path | None,
                backfill: bool) -> None:
    keys = json.loads(keys_path.read_text(encoding="utf-8")) if keys_path else None
    client = None
    if backfill:
        from app.features.mentor.client import get_mentor_client
        client = get_mentor_client()
    async with async_session_maker() as db:
        changes = await rescore_all(db, apply, engine, set(keys.values()) if keys else None, client)
    for c in changes:
        print(f"attempt {c['attempt_id']:>6}  {c['exercise']:<8}  {c['old']:6.2f} -> {c['new']:6.2f}")
        if details:
            print(f"    kind={c['kind']}  explain-back={c['explanation']:.1f}/20")
            for axis in _AXIS_COLUMNS:
                level = f"  level {c['levels'][axis]}" if c["levels"] and c["levels"][axis] is not None else ""
                print(f"    {axis:<13} {_fmt(c['axes_old'][axis])} -> {_fmt(c['axes_new'][axis])}{level}")
    if out:
        out.write_text(json.dumps(engine_json(changes, keys) if keys else changes, indent=2), encoding="utf-8")
        print(f"written {out}")
    verb = "rescored" if apply else "would rescore (dry run, use --apply to write)"
    print(f"{len(changes)} report(s) {verb} with engine {engine}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="write the new scores (default: dry run)")
    parser.add_argument("--details", action="store_true", help="print every axis, old -> new")
    parser.add_argument("--engine", choices=("v1", "v2"), default="v1")
    parser.add_argument("--keys", type=Path, help="golden-set keys.json: rescore only these attempts")
    parser.add_argument("--out", type=Path, help="write the results as JSON (engine.json shape with --keys)")
    parser.add_argument("--backfill-judges", action="store_true",
                        help="v2: ask the LLM once for missing rubric verdicts and store them")
    args = parser.parse_args()
    if args.backfill_judges and args.engine != "v2":
        parser.error("--backfill-judges only applies to --engine v2")
    asyncio.run(_main(args.apply, args.details, args.engine, args.keys, args.out, args.backfill_judges))
