from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user
from app.features.attempts import service as attempts_service
from app.features.mentor import service
from app.models import User
from app.schemas.mentor import HypothesisIn, HypothesisOut, MentorIn, MentorOut

router = APIRouter(prefix="/api/attempts", tags=["mentor"])


@router.post("/{attempt_id}/mentor", response_model=MentorOut)
async def mentor(
    attempt_id: int,
    data: MentorIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MentorOut:
    attempt = await attempts_service.require_attempt(db, attempt_id, user)
    out = await service.mentor_reply(db, attempt, data.message, data.code)
    return MentorOut(**out)


@router.post("/{attempt_id}/hypothesis", response_model=HypothesisOut)
async def hypothesis(
    attempt_id: int,
    data: HypothesisIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> HypothesisOut:
    attempt = await attempts_service.require_attempt(db, attempt_id, user)
    out = await service.judge_hypothesis(db, attempt, data.text)
    return HypothesisOut(**out)
