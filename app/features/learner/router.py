from typing import Literal

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user
from app.features.learner.brief import learner_brief
from app.features.learner.profile import LearnerProfile, profile
from app.models import User

router = APIRouter(prefix="/api/learner", tags=["learner"])


class LearnerOut(LearnerProfile):
    brief: str


@router.get("/me", response_model=LearnerOut)
async def my_learner_profile(locale: Literal["vi", "en"] = "vi", db: AsyncSession = Depends(get_db),
                             user: User = Depends(get_current_user)) -> LearnerOut:
    """The current student's skill ratings, axis profile, recurring issues and brief (P3.3). Own data only."""
    p = await profile(db, user.id)
    return LearnerOut(**p.model_dump(), brief=learner_brief(p, locale))
