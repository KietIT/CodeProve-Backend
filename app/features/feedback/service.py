"""The report's `feedback.diagnosis` (P1.5): findings plus the text explaining them.

`build_diagnosis` runs when an attempt is scored: diagnose, pick next-exercise
candidates, and ask the writer once. `refresh_diagnosis` runs on a rescore and
never calls the LLM: a finding whose code and params are unchanged keeps its
stored text, anything else gets its template.
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.feedback.diagnosis import diagnose
from app.features.feedback.next_exercise import candidates
from app.features.feedback.templates import DEFAULT_LOCALE, render
from app.features.feedback.writer import write_feedback
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
                                   final_code=ev.final_code, answers=ev.answers, candidates=suggested)
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
        old = kept.get(finding.code)
        if old and old.get("params") == finding.params and old.get("text"):
            entries.append({**finding.model_dump(), "text": old["text"], "next_exercise": old.get("next_exercise"),
                            "source": old.get("source", "template")})
        else:
            entries.append({**finding.model_dump(), "text": render(finding, locale, fallback_next),
                            "next_exercise": fallback_next, "source": "template"})
    return {"version": VERSION, "locale": locale, "model": previous.get("model"), "findings": entries}
