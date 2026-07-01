from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user
from app.features.exercises import service
from app.models import User
from app.schemas.exercise import ExerciseDetail, LevelGroup

router = APIRouter(prefix="/api/exercises", tags=["exercises"])


@router.get("", response_model=list[LevelGroup])
async def list_exercises(level: str | None = None, db: AsyncSession = Depends(get_db),
                         user: User = Depends(get_current_user)) -> list[dict]:
    return await service.list_grouped(db, level, user.id)


@router.get("/{code}", response_model=ExerciseDetail)
async def get_exercise(code: str, db: AsyncSession = Depends(get_db),
                       _: User = Depends(get_current_user)) -> dict:
    detail = await service.get_detail(db, code)
    if detail is None:
        raise HTTPException(status_code=404, detail="Exercise not found")
    return detail
