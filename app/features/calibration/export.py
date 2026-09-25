"""Export anonymised sessions for the golden set (P1.3).

    python -m app.features.calibration.export --out DIR [--limit 60] [--per-user 3]
        [--email-like PATTERN] [--keys-out FILE]

Writes DIR/sessions.json (what the raters see) and DIR/engine.json (the
engine's scores per session, kept away from the raters so they are not
anchored). --email-like restricts the set to matching accounts (SQL LIKE, e.g.
the simulated 'calib.sim%@example.com'); --keys-out writes the private
session-id -> attempt-id map the analysis needs to join intended profiles. Session ids are derived from a random salt that is never stored,
so they cannot be traced back to a user. Only minutes relative to the start
are kept, never timestamps. Emails and phone numbers are scrubbed from free
text; a name someone typed into a prompt is not, so spot-check before sharing.
"""
import argparse
import asyncio
import hashlib
import json
import re
import secrets
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import async_session_maker
from app.models import Attempt, CodeSnapshot, Event, Exercise, FluencyReport, PromptLog, User, VerificationAnswer

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"(?<!\d)(?:\+84|0)\d{9,10}(?!\d)")
_INTEGRITY = {
    "paste_blocked": lambda e: "PASTE_BLOCKED" in e["integrity_flags"] or e["type"] == "BURST_PASTE",
    "tab_hidden": lambda e: e["type"] == "TAB_HIDDEN",
    "window_blur": lambda e: e["type"] == "WINDOW_BLUR",
    "fullscreen_exit": lambda e: e["type"] == "FULLSCREEN_EXIT",
    "focus_lost": lambda e: e["type"] == "FOCUS_LOST",
}


def scrub(text: str | None) -> str:
    if not text:
        return ""
    return _PHONE.sub("[số điện thoại]", _EMAIL.sub("[email]", text))


def _minutes(ts: int, start: int) -> float:
    return round((ts - start) / 60000, 1)


async def _rows(db: AsyncSession, model, attempt_id: int, order):
    return (await db.execute(select(model).where(model.attempt_id == attempt_id).order_by(order))).scalars().all()


async def _session(db: AsyncSession, sid: str, attempt: Attempt, ex: Exercise) -> dict | None:
    snapshots = await _rows(db, CodeSnapshot, attempt.id, CodeSnapshot.version.desc())
    answers = await _rows(db, VerificationAnswer, attempt.id, VerificationAnswer.id)
    if not snapshots or not answers:
        return None  # nothing a rater could judge
    events = [{"type": e.type, "ts": e.ts, "payload": e.payload or {}, "integrity_flags": e.integrity_flags or []}
              for e in await _rows(db, Event, attempt.id, Event.ts)]
    if not events:
        return None
    start = next((e["ts"] for e in events if e["type"] == "OPEN"), events[0]["ts"])
    # Time spent solving: an explain-back answered much later must not inflate it.
    end = next((e["ts"] for e in events if e["type"] == "SUBMIT"), events[-1]["ts"])
    replies = [e for e in events if e["type"] == "AI_REPLY"]
    prompts = await _rows(db, PromptLog, attempt.id, PromptLog.id)
    submits = [e["payload"] for e in events if e["type"] == "SUBMIT_TESTS"]
    return {
        "id": sid,
        "exercise": {"code": ex.code, "title": ex.title, "kind": ex.kind, "level": ex.level, "summary": ex.summary},
        "duration_min": _minutes(end, start),
        "hypotheses": [
            {"at_min": _minutes(e["ts"], start), "text": scrub(e["payload"].get("text")) or None,
             "correct": e["payload"].get("correct")}
            for e in events if e["type"] == "HYPOTHESIS"
        ],
        "prompts": [
            {"prompt": scrub(p.prompt), "reply": scrub(p.response),
             # AI_REPLY events and prompt logs are written in the same order.
             "planted_bug": bool(replies[i]["payload"].get("injectedError")) if i < len(replies) else False}
            for i, p in enumerate(prompts)
        ],
        "runs": [
            {"at_min": _minutes(e["ts"], start), "pass_ratio": e["payload"].get("passRatio"),
             "starter": bool(e["payload"].get("isStarter"))}
            for e in events if e["type"] == "RUN"
        ],
        "submit_tests": (
            {"passed": submits[-1].get("passed"), "total": submits[-1].get("total"),
             "hidden_passed": submits[-1].get("hiddenPassed"), "hidden_total": submits[-1].get("hiddenTotal"),
             "failed_categories": submits[-1].get("failedCategories", []),
             "failures": submits[-1].get("failures", [])}
            if submits else None
        ),
        "final_code": snapshots[0].source_code,
        "explain_back": [{"question": scrub(a.question), "answer": scrub(a.answer)} for a in answers],
        "integrity": {name: sum(1 for e in events if match(e)) for name, match in _INTEGRITY.items()},
    }


async def build_sessions(db: AsyncSession, limit: int = 60, per_user: int = 3, salt: str | None = None,
                         email_like: str | None = None) -> tuple[list[dict], dict, dict]:
    """(sessions, engine scores by session id, attempt id by session id)."""
    salt = salt or secrets.token_hex(16)
    query = (
        select(Attempt, Exercise, FluencyReport)
        .join(Exercise, Exercise.id == Attempt.exercise_id)
        .join(FluencyReport, FluencyReport.attempt_id == Attempt.id)
        .where(Attempt.status == "scored")
        .order_by(Attempt.id.desc())
    )
    if email_like:
        query = query.join(User, User.id == Attempt.user_id).where(User.email.like(email_like))
    rows = (await db.execute(query)).all()
    sessions: list[dict] = []
    engine: dict[str, dict] = {}
    keys: dict[str, int] = {}
    taken: dict[int, int] = {}
    for attempt, ex, report in rows:
        if len(sessions) >= limit:
            break
        if taken.get(attempt.user_id, 0) >= per_user:
            continue  # keep the set diverse: no single person dominates it
        sid = "S" + hashlib.sha256(f"{salt}:{attempt.id}".encode()).hexdigest()[:8]
        session = await _session(db, sid, attempt, ex)
        if session is None:
            continue
        sessions.append(session)
        taken[attempt.user_id] = taken.get(attempt.user_id, 0) + 1
        keys[sid] = attempt.id
        engine[sid] = {
            "overall": report.overall_score,
            "axes": {"understanding": report.understanding_score, "hypothesis": report.hypothesis_score,
                     "prompting": report.prompt_score, "verification": report.verification_score,
                     "testing": report.testing_score, "debugging": report.debugging_score},
        }
    return sessions, engine, keys


async def _main(out: Path, limit: int, per_user: int, email_like: str | None, keys_out: Path | None) -> None:
    async with async_session_maker() as db:
        sessions, engine, keys = await build_sessions(db, limit, per_user, email_like=email_like)
    out.mkdir(parents=True, exist_ok=True)
    (out / "sessions.json").write_text(json.dumps(sessions, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "engine.json").write_text(json.dumps(engine, ensure_ascii=False, indent=2), encoding="utf-8")
    if keys_out:
        keys_out.parent.mkdir(parents=True, exist_ok=True)
        keys_out.write_text(json.dumps(keys, indent=2), encoding="utf-8")
    print(f"{len(sessions)} session(s) written to {out}")
    if len(sessions) < 40:
        print("warning: fewer than 40 sessions; the golden set needs ~40 with real work")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=60)
    parser.add_argument("--per-user", type=int, default=3)
    parser.add_argument("--email-like", default=None, help="only accounts whose email matches (SQL LIKE)")
    parser.add_argument("--keys-out", type=Path, default=None, help="private session-id -> attempt-id map")
    args = parser.parse_args()
    asyncio.run(_main(args.out, args.limit, args.per_user, args.email_like, args.keys_out))
