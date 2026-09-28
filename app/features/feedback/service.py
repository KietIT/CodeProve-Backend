"""The report's `feedback.diagnosis` (P1.5): findings plus the text explaining them.

`build_diagnosis` runs when an attempt is scored: diagnose, pick next-exercise
candidates, and ask the writer once. `refresh_diagnosis` runs on a rescore and
never calls the LLM: every field comes from the current templates, except a
stored LLM `what_happened` of a finding the writer still writes (WRITTEN_CODES)
whose params are unchanged.
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.feedback.diagnosis import diagnose
from app.features.feedback.next_exercise import candidates
from app.features.feedback.templates import DEFAULT_LOCALE, render
from app.features.feedback.writer import WRITTEN_CODES, write_feedback
from app.features.scoring.evidence import Evidence
from app.models import Attempt, Exercise

VERSION = 1


def submit_locale(ev: Evidence) -> str:
    """The language the student used, as sent with Submit (default Vietnamese)."""
    submits = [e["payload"] for e in ev.events if e["type"] == "SUBMIT"]
    locale = submits[-1].get("locale") if submits else None
    return locale if locale in ("vi", "en") else DEFAULT_LOCALE


async def build_diagnosis(db: AsyncSession, attempt: Attempt, exercise: Exercise, ev: Evidence, result: dict,
                          client, locale: str | None = None) -> dict:
    locale = locale or submit_locale(ev)
    findings = diagnose(result, ev)
    suggested = await candidates(db, attempt.user_id, exercise, findings)
    entries = await write_feedback(client, locale=locale, problem=exercise.summary or "", findings=findings,
                                   answers=ev.answers, candidates=suggested)
    return {"version": VERSION, "locale": locale, "model": client._model, "candidates": suggested,
            "findings": entries}


async def refresh_diagnosis(db: AsyncSession, attempt: Attempt, exercise: Exercise, ev: Evidence, result: dict,
                            previous: dict | None) -> dict:
    previous = previous or {}
    locale = previous.get("locale") or submit_locale(ev)
    findings = diagnose(result, ev)
    suggested = await candidates(db, attempt.user_id, exercise, findings)
    fallback_next = suggested[0] if suggested else None
    kept = {e.get("code"): e for e in previous.get("findings") or []}
    entries = []
    for finding in findings:
        text = render(finding, locale, fallback_next)
        entry = {**finding.model_dump(), "text": text, "next_exercise": fallback_next, "source": "template"}
        old = kept.get(finding.code)
        # Only a line the writer may still write survives: older reports hold LLM lines on
        # strengths that restated the solution (team review of round 3).
        if (finding.code in WRITTEN_CODES and old and old.get("source") == "llm"
                and old.get("params") == finding.params and (old.get("text") or {}).get("what_happened")):
            text["what_happened"] = old["text"]["what_happened"]
            entry["source"] = "llm"
        entries.append(entry)
    return {"version": VERSION, "locale": locale, "model": previous.get("model"), "findings": entries}
