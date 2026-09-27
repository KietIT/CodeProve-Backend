"""Preview and check the written feedback on the golden set (P1.5, Task 6).

    python -m app.features.feedback.preview run --keys keys.json --out feedback_preview.json [--locale auto]
    python -m app.features.feedback.preview check --preview feedback_preview.json

`run` builds the diagnosis and asks the writer for each golden-set attempt,
exactly as at explain-back, but stores nothing (no report, no event). It
reads the rubric verdicts already stored for those attempts. `--locale auto`
guesses the language from the explain-back questions (sessions submitted
before the locale was recorded). `check` looks for solution leaks and invalid
items; it exits with status 1 when it finds a leak.
"""
import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.content.schema import CONTENT_DIR, load_content_file
from app.features.feedback.service import build_diagnosis
from app.features.scoring.engine_v2 import score_attempt_v2
from app.features.scoring.evidence import Evidence, code_lines, load_evidence
from app.models import Attempt, Exercise, FluencyReport

_VIETNAMESE = re.compile(r"[ăâđêôơưàáạảãèéẹẻẽìíịỉĩòóọỏõùúụủũỳýỵỷỹ]", re.IGNORECASE)
_BLOCK = re.compile(r"```[\w+-]*\n?(.*?)```", re.DOTALL)
_EXERCISE = re.compile(r"\bCP-\d{3}\b")
MIN_LEAK_CHARS = 20  # shorter lines ("return []", "seen = {}") are too generic to count as a leak
LEAKS = {"long_code_block", "reference_line_copied"}


def guess_locale(ev: Evidence) -> str:
    text = " ".join(a.get("question") or "" for a in ev.answers)
    if not text.strip():
        return "vi"
    return "vi" if _VIETNAMESE.search(text) else "en"


async def preview_all(db: AsyncSession, keys: dict[str, int], client, locale: str = "auto") -> dict:
    out = {}
    for sid, attempt_id in keys.items():
        row = (await db.execute(
            select(Attempt, Exercise, FluencyReport)
            .join(Exercise, Exercise.id == Attempt.exercise_id)
            .join(FluencyReport, FluencyReport.attempt_id == Attempt.id)
            .where(Attempt.id == attempt_id))).first()
        if row is None:
            continue
        attempt, exercise, report = row
        ev = await load_evidence(db, attempt)
        result = score_attempt_v2(ev, report.explanation_score)
        chosen = guess_locale(ev) if locale == "auto" else locale
        diagnosis = await build_diagnosis(db, attempt, exercise, ev, result, client, locale=chosen)
        out[sid] = {"exercise": exercise.code, "locale": diagnosis["locale"], "final_code": ev.final_code,
                    "candidates": diagnosis["candidates"], "findings": diagnosis["findings"]}
    return out


def check(previews: dict, references: dict[str, str]) -> list[dict]:
    """Issues in the written feedback: leaks (long code, copied reference lines) and invalid items."""
    issues = []
    for sid, p in previews.items():
        own = set(code_lines(p.get("final_code") or ""))
        leak_lines = [line for line in code_lines(references.get(p["exercise"], ""))
                      if len(line) >= MIN_LEAK_CHARS and line not in own]
        for entry in p["findings"]:
            texts = entry.get("text") or {}
            joined = " ".join(texts.values())

            def issue(kind: str, detail: str = "") -> None:
                issues.append({"session": sid, "code": entry["code"], "source": entry.get("source"),
                               "issue": kind, "detail": detail})

            for block in _BLOCK.findall(joined):
                if len([line for line in block.split("\n") if line.strip()]) > 2:
                    issue("long_code_block", block.strip()[:80])
            for line in leak_lines:
                if line in joined:
                    issue("reference_line_copied", line)
            if entry.get("next_exercise") and entry["next_exercise"] not in p["candidates"]:
                issue("next_not_a_candidate", entry["next_exercise"])
            for code in set(_EXERCISE.findall(joined)) - set(p["candidates"]):
                issue("exercise_not_a_candidate", code)
    return issues


def _references(content_dir: Path) -> dict[str, str]:
    return {c.code: c.reference_solution for c in map(load_content_file, sorted(content_dir.glob("CP-*.json")))}


async def _run(keys_path: Path, out: Path, locale: str) -> None:
    from app.core.db import async_session_maker
    from app.features.mentor.client import get_mentor_client

    keys = json.loads(keys_path.read_text(encoding="utf-8"))
    async with async_session_maker() as db:
        previews = await preview_all(db, keys, get_mentor_client(), locale)
    out.write_text(json.dumps(previews, ensure_ascii=False, indent=2), encoding="utf-8")
    written = sum(e["source"] == "llm" for p in previews.values() for e in p["findings"])
    total = sum(len(p["findings"]) for p in previews.values())
    print(f"{len(previews)} session(s), {total} finding(s), {written} written by the LLM -> {out}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run")
    run.add_argument("--keys", type=Path, required=True)
    run.add_argument("--out", type=Path, required=True)
    run.add_argument("--locale", choices=("auto", "vi", "en"), default="auto")
    chk = sub.add_parser("check")
    chk.add_argument("--preview", type=Path, required=True)
    chk.add_argument("--content-dir", type=Path, default=CONTENT_DIR)
    args = parser.parse_args()
    if args.cmd == "run":
        asyncio.run(_run(args.keys, args.out, args.locale))
        return
    issues = check(json.loads(args.preview.read_text(encoding="utf-8")), _references(args.content_dir))
    for i in issues:
        print(f"{i['session']} {i['code']:<22} {i['source']:<8} {i['issue']}: {i['detail']}")
    leaks = sum(i["issue"] in LEAKS for i in issues)
    print(f"{len(issues)} issue(s), {leaks} leak(s)")
    sys.exit(1 if leaks else 0)


if __name__ == "__main__":
    main()
