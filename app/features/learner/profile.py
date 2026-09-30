"""What the system knows about a student (P3.3): skill ratings, axis profile, recurring issues.

Computed on read from `learner_skills` and the student's recent reports; nothing
here is stored. Only v2 reports carry axis levels and findings, so the axis
profile and recurring issues use the last WINDOW of those.
"""
from collections import Counter

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.content.skills import TAXONOMY
from app.features.scoring.engine_v2 import AXES
from app.models import Attempt, FluencyReport, LearnerSkill

WINDOW = 5
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


class LearnerProfile(BaseModel):
    scored_attempts: int
    skills: list[SkillRating]  # highest rating first
    axes: dict[str, float | None]  # mean level 0-3 over the window; None = never applicable
    recurring: list[RecurringIssue]  # most frequent first
    window: int  # v2 reports the axes and recurring issues are based on


def axis_profile(feedbacks: list[dict]) -> dict[str, float | None]:
    means: dict[str, float | None] = {}
    for axis in AXES:
        levels = [fb["levels"][axis] for fb in feedbacks if fb["levels"].get(axis) is not None]
        means[axis] = round(sum(levels) / len(levels), 2) if levels else None
    return means


def recurring_issues(feedbacks: list[dict]) -> list[RecurringIssue]:
    counts: Counter[str] = Counter()
    for fb in feedbacks:
        findings = (fb.get("diagnosis") or {}).get("findings") or []
        counts.update({f["code"] for f in findings if f.get("kind") == "risk" and f.get("code")})
    return [RecurringIssue(code=code, count=n)
            for code, n in sorted(counts.items(), key=lambda item: (-item[1], item[0])) if n >= MIN_REPEATS]


async def _recent_v2_feedback(db: AsyncSession, user_id: int) -> list[dict]:
    rows = (await db.execute(
        select(FluencyReport.feedback).join(Attempt, Attempt.id == FluencyReport.attempt_id)
        .where(Attempt.user_id == user_id)
        .order_by(func.coalesce(Attempt.submitted_at, FluencyReport.created_at).desc(), FluencyReport.id.desc())
        .limit(_SCAN_LIMIT)
    )).scalars().all()
    return [fb for fb in rows if isinstance(fb, dict) and isinstance(fb.get("levels"), dict)][:WINDOW]


async def profile(db: AsyncSession, user_id: int) -> LearnerProfile:
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
                          recurring=recurring_issues(feedbacks), window=len(feedbacks))
