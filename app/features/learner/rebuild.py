"""Recompute the learner model (P3.3) from every stored report.

Run once after deploying P3.3 (backfill) and again after any rescore:

    python -m app.features.learner.rebuild           # dry run: counts only
    python -m app.features.learner.rebuild --apply   # replace learner_skills and exercise difficulties
"""
import argparse
import asyncio

from sqlalchemy import select

from app.core.db import async_session_maker
from app.features.learner import elo
from app.features.learner.service import rebuild
from app.models import Exercise

TOP_MOVED = 5


async def _main(apply: bool) -> int:
    async with async_session_maker() as db:
        exercises = {ex.id: ex for ex in (await db.execute(select(Exercise))).scalars()}
        result = await rebuild(db, apply)
    print(f"{result.reports} scored report(s) replayed, {result.students} student(s), "
          f"{len(result.ratings)} skill rating(s), {len(result.difficulties)} exercise(s) rated")
    moved = sorted(result.difficulties.items(),
                   key=lambda item: -abs(item[1] - elo.difficulty(None, exercises[item[0]].level)))
    for ex_id, d in moved[:TOP_MOVED]:
        ex = exercises[ex_id]
        print(f"  {ex.code} ({ex.level}) difficulty {elo.difficulty(None, ex.level):.0f} -> {d:.0f}")
    print("written" if apply else "dry run, use --apply to write")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="write the recomputed model")
    raise SystemExit(asyncio.run(_main(parser.parse_args().apply)))
