"""Real learner counts and recent accounts for the admin overview."""
from datetime import datetime

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.features.admin.router import Principal, ready_admin
from app.models import Attempt, User

router = APIRouter(prefix="/api/admin", tags=["admin overview"])


class RecentLearner(BaseModel):
    id: int
    full_name: str
    email: str
    created_at: datetime


class OverviewOut(BaseModel):
    users_total: int
    users_active: int
    attempts_total: int
    recent_users: list[RecentLearner]


@router.get("/overview", response_model=OverviewOut)
async def overview(
    response: Response,
    _principal: Principal = Depends(ready_admin),
    db: AsyncSession = Depends(get_db),
) -> OverviewOut:
    response.headers["Cache-Control"] = "no-store"
    users_total, users_active = (await db.execute(
        select(
            func.count(User.id),
            func.coalesce(func.sum(case((User.is_active.is_(True), 1), else_=0)), 0),
        ).where(User.role == "user")
    )).one()
    attempts_total = (await db.scalar(
        select(func.count(Attempt.id)).join(User, Attempt.user_id == User.id).where(User.role == "user")
    )) or 0
    recent = (await db.execute(
        select(User.id, User.full_name, User.email, User.created_at)
        .where(User.role == "user")
        .order_by(User.created_at.desc(), User.id.desc())
        .limit(4)
    )).all()
    return OverviewOut(
        users_total=users_total,
        users_active=users_active,
        attempts_total=attempts_total,
        recent_users=[RecentLearner(id=id, full_name=name, email=email, created_at=created_at)
                      for id, name, email, created_at in recent],
    )
