"""What the system knows about a student (P3.3): skill ratings, axis profile, recurring issues.

Computed on read from `learner_skills` and the student's recent reports; nothing
here is stored. Only v2 reports carry axis levels and findings, so the axis
profile and recurring issues use the last WINDOW of those. `history` (P3.5,
for the progress page) lists the last HISTORY scored reports of any engine.
"""
from collections import Counter
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.content.skills import TAXONOMY
from app.features.feedback.templates import TEMPLATES
from app.features.scoring.engine_v2 import AXES
from app.models import Attempt, Exercise, FluencyReport, LearnerSkill

WINDOW = 5
HISTORY = 10
MIN_REPEATS = 2  # a risk seen in at least this many of the window's reports is "recurring"
_SCAN_LIMIT = 50  # recent reports scanned to find WINDOW v2 ones


class SkillRating(BaseModel):
    key: str
    vi: str
    en: str
    rating: float
    attempts: int


class RecurringIssue(BaseModel):
    code: str
    count: int  # reports of the window where it appeared
    practice: str = ""  # the team-reviewed `practice` phrase of its template, in the requested locale


class HistoryItem(BaseModel):
    date: datetime  # submit time (report time for attempts without one)
    code: str
    title: str
    overall: float
    levels: dict[str, int | None] | None  # None for v1 reports, which have no axis levels


class LearnerProfile(BaseModel):
    scored_attempts: int
    skills: list[SkillRating]  # highest rating first
    axes: dict[str, float | None]  # mean level 0-3 over the window; None = never applicable
    recurring: list[RecurringIssue]  # most frequent first
    window: int  # v2 reports the axes and recurring issues are based on
    history: list[HistoryItem] = []  # last HISTORY scored reports, oldest first


def axis_profile(feedbacks: list[dict]) -> dict[str, float | None]:
    means: dict[str, float | None] = {}
    for axis in AXES:
        levels = [fb["levels"][axis] for fb in feedbacks if fb["levels"].get(axis) is not None]
        means[axis] = round(sum(levels) / len(levels), 2) if levels else None
    return means


def recurring_issues(feedbacks: list[dict], locale: str = "vi") -> list[RecurringIssue]:
    counts: Counter[str] = Counter()
    for fb in feedbacks:
        findings = (fb.get("diagnosis") or {}).get("findings") or []
        counts.update({f["code"] for f in findings if f.get("kind") == "risk" and f.get("code")})
    def practice(code: str) -> str:
        return TEMPLATES.get(code, {}).get(locale, {}).get("practice", "")

    return [RecurringIssue(code=code, count=n, practice=practice(code))
            for code, n in sorted(counts.items(), key=lambda item: (-item[1], item[0])) if n >= MIN_REPEATS]


async def _recent_v2_feedback(db: AsyncSession, user_id: int) -> list[dict]:
    rows = (await db.execute(
        select(FluencyReport.feedback).join(Attempt, Attempt.id == FluencyReport.attempt_id)
        .where(Attempt.user_id == user_id)
        .order_by(func.coalesce(Attempt.submitted_at, FluencyReport.created_at).desc(), FluencyReport.id.desc())
        .limit(_SCAN_LIMIT)
    )).scalars().all()
    return [fb for fb in rows if isinstance(fb, dict) and isinstance(fb.get("levels"), dict)][:WINDOW]


async def _history(db: AsyncSession, user_id: int) -> list[HistoryItem]:
    when = func.coalesce(Attempt.submitted_at, FluencyReport.created_at)
    rows = (await db.execute(
        select(when, Exercise.code, Exercise.title, FluencyReport.overall_score, FluencyReport.feedback)
        .join(Attempt, Attempt.id == FluencyReport.attempt_id).join(Exercise, Exercise.id == Attempt.exercise_id)
        .where(Attempt.user_id == user_id).order_by(when.desc(), FluencyReport.id.desc()).limit(HISTORY)
    )).all()
    items = []
    for date, code, title, overall, fb in reversed(rows):
        levels = fb.get("levels") if isinstance(fb, dict) and isinstance(fb.get("levels"), dict) else None
        items.append(HistoryItem(date=date, code=code, title=title, overall=round(overall or 0.0, 1), levels=levels))
    return items


async def profile(db: AsyncSession, user_id: int, locale: str = "vi") -> LearnerProfile:
    scored = (await db.execute(
        select(func.count()).select_from(FluencyReport).join(Attempt, Attempt.id == FluencyReport.attempt_id)
        .where(Attempt.user_id == user_id)
    )).scalar_one()
    rows = (await db.execute(select(LearnerSkill).where(LearnerSkill.user_id == user_id))).scalars().all()
    skills = sorted(
        (SkillRating(key=r.skill, rating=round(r.rating, 1), attempts=r.attempts, **TAXONOMY[r.skill])
         for r in rows if r.skill in TAXONOMY),  # a key retired from the taxonomy is not shown
        key=lambda s: (-s.rating, s.key),
    )
    feedbacks = await _recent_v2_feedback(db, user_id)
    return LearnerProfile(scored_attempts=scored, skills=skills, axes=axis_profile(feedbacks),
                          recurring=recurring_issues(feedbacks, locale), window=len(feedbacks),
                          history=await _history(db, user_id))
