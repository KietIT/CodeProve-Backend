"""Read-only learner directory for authenticated administrators."""
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.features.admin.router import Principal, ready_admin
from app.models import Attempt, User

router = APIRouter(prefix="/api/admin/users", tags=["admin users"])


class LearnerOut(BaseModel):
    id: int
    full_name: str
    email: str
    is_active: bool
    created_at: datetime
    last_attempt_at: datetime | None
    attempts: int
    completed: int
    average_score: float | None


class LearnerPage(BaseModel):
    items: list[LearnerOut]
    total: int
    limit: int
    offset: int


async def attempt_stats(db: AsyncSession, user_ids: list[int]) -> dict[int, tuple[int, int, float | None, datetime | None]]:
    if not user_ids:
        return {}
    rows = (await db.execute(
        select(
            Attempt.user_id,
            func.count(Attempt.id),
            func.sum(case((Attempt.status.in_(("submitted", "scored")), 1), else_=0)),
            func.avg(case((Attempt.status == "scored", Attempt.score))),
            func.max(Attempt.started_at),
        ).where(Attempt.user_id.in_(user_ids)).group_by(Attempt.user_id)
    )).all()
    return {user_id: (count, completed, average, last) for user_id, count, completed, average, last in rows}


def learner_out(user: User, stats: dict[int, tuple[int, int, float | None, datetime | None]]) -> LearnerOut:
    attempts, completed, average, last = stats.get(user.id, (0, 0, None, None))
    return LearnerOut(
        id=user.id, full_name=user.full_name, email=user.email, is_active=user.is_active,
        created_at=user.created_at, last_attempt_at=last, attempts=attempts,
        completed=completed, average_score=round(float(average), 1) if average is not None else None,
    )


@router.get("", response_model=LearnerPage)
async def list_users(
    response: Response,
    search: str = Query("", max_length=100),
    account_status: Literal["active", "inactive"] | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _principal: Principal = Depends(ready_admin),
    db: AsyncSession = Depends(get_db),
) -> LearnerPage:
    response.headers["Cache-Control"] = "no-store"
    filters = [User.role == "user"]
    if account_status is not None:
        filters.append(User.is_active.is_(account_status == "active"))
    term = search.strip()
    if term:
        escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        matches = [User.full_name.ilike(f"%{escaped}%", escape="\\"), User.email.ilike(f"%{escaped}%", escape="\\")]
        if term.isdecimal():
            matches.append(User.id == int(term))
        filters.append(or_(*matches))
    total = (await db.scalar(select(func.count(User.id)).where(*filters))) or 0
    people = (await db.execute(
        select(User).where(*filters).order_by(User.created_at.desc(), User.id.desc()).limit(limit).offset(offset)
    )).scalars().all()
    stats = await attempt_stats(db, [person.id for person in people])
    return LearnerPage(items=[learner_out(person, stats) for person in people], total=total, limit=limit, offset=offset)


@router.get("/{user_id}", response_model=LearnerOut)
async def get_user(
    user_id: int,
    response: Response,
    _principal: Principal = Depends(ready_admin),
    db: AsyncSession = Depends(get_db),
) -> LearnerOut:
    response.headers["Cache-Control"] = "no-store"
    user = (await db.execute(select(User).where(User.id == user_id, User.role == "user"))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return learner_out(user, await attempt_stats(db, [user.id]))
