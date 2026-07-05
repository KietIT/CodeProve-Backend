from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.core.deps import get_current_user_optional
from app.features.daily import service
from app.models import DailyChallenge, User
from app.schemas.daily import DailyAttemptIn, DailyAttemptOut, DailyChallengeOut, DailyResult

router = APIRouter(prefix="/api/daily", tags=["daily"])


@router.get("/today", response_model=DailyChallengeOut)
async def today(
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
) -> DailyChallengeOut:
    d = service.today_vn()
    challenge = await service.get_or_create_challenge(db, d)
    num = await service.challenge_number(db, d)

    result = None
    already_played = False
    if user is not None:
        attempt = await service.get_attempt(db, user.id, d)
        if attempt is not None and attempt.submitted_at is not None:
            already_played = True
            result = DailyResult(
                correct=attempt.selected_line == challenge.buggy_line,
                tier=attempt.tier or "red",
                buggy_line=challenge.buggy_line,
                explanation=challenge.explanation,
                hints_used=attempt.hints_used,
                time_taken_seconds=attempt.time_taken_seconds or 0,
            )
    return DailyChallengeOut(
        challenge_number=num,
        prompt_title=challenge.prompt_title,
        buggy_code=challenge.buggy_code,
        already_played=already_played,
        result=result,
    )


@router.post("/attempt", response_model=DailyAttemptOut)
async def attempt(
    data: DailyAttemptIn,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
) -> DailyAttemptOut:
    today_date = service.today_vn()
    if user is not None:
        existing = await service.get_attempt(db, user.id, today_date)
        if existing is not None and existing.submitted_at is not None:
            raise HTTPException(status_code=409, detail="Already played today")
    result = await service.submit_attempt(
        db,
        user.id if user is not None else None,
        data.selected_line,
        data.hints_used,
        data.time_taken_seconds,
    )
    return DailyAttemptOut(**result)


@router.post("/regenerate")
async def regenerate(
    x_admin_key: str = Header(default=""),
    db: AsyncSession = Depends(get_db),
) -> dict:
    settings = get_settings()
    if not settings.admin_api_key or x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=403, detail="Forbidden")
    d = service.today_vn()
    existing = (
        await db.execute(select(DailyChallenge).where(DailyChallenge.challenge_date == d))
    ).scalar_one_or_none()
    if existing is not None:
        await db.delete(existing)
        await db.commit()
    challenge = await service.get_or_create_challenge(db, d)
    return {"regenerated": True, "prompt_title": challenge.prompt_title}
