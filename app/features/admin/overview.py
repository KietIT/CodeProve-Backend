"""Real learner counts and recent accounts for the admin overview."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.features.admin.router import Principal, ready_admin
from app.features.mentor.cost_report import month_bounds
from app.models import Attempt, Order, Subscription, User

router = APIRouter(prefix="/api/admin", tags=["admin overview"])


class RecentLearner(BaseModel):
    id: int
    full_name: str
    email: str
    created_at: datetime


class PlanCounts(BaseModel):
    free: int
    plus: int
    pro: int


class OverviewOut(BaseModel):
    users_total: int
    users_active: int
    attempts_total: int
    recent_users: list[RecentLearner]
    # Learners by the plan running right now, and money from paid orders (VND). A plan given by hand has no
    # order, so it counts in plan_counts but not in revenue. "This month" is the calendar month in quota_timezone.
    plan_counts: PlanCounts
    orders_paid_total: int
    orders_paid_this_month: int
    revenue_total: int
    revenue_this_month: int


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
    now = datetime.now(ZoneInfo(get_settings().quota_timezone))
    month_start, month_end = month_bounds(now.strftime("%Y-%m"), get_settings().quota_timezone)
    running = dict((await db.execute(
        select(Subscription.tier, func.count(Subscription.id))
        .join(User, Subscription.user_id == User.id)
        .where(User.role == "user", Subscription.expires_at > datetime.now(timezone.utc))
        .group_by(Subscription.tier)
    )).all())
    plus, pro = running.get("plus", 0), running.get("pro", 0)
    in_month = Order.paid_at >= month_start
    paid_total, revenue_total, paid_month, revenue_month = (await db.execute(
        select(
            func.count(Order.id),
            func.coalesce(func.sum(Order.amount), 0),
            func.coalesce(func.sum(case((in_month, 1), else_=0)), 0),
            func.coalesce(func.sum(case((in_month, Order.amount), else_=0)), 0),
        ).where(Order.status == "paid", Order.paid_at < month_end)
    )).one()
    return OverviewOut(
        plan_counts=PlanCounts(free=users_total - plus - pro, plus=plus, pro=pro),
        orders_paid_total=paid_total,
        orders_paid_this_month=paid_month,
        revenue_total=revenue_total,
        revenue_this_month=revenue_month,
        users_total=users_total,
        users_active=users_active,
        attempts_total=attempts_total,
        recent_users=[RecentLearner(id=id, full_name=name, email=email, created_at=created_at)
                      for id, name, email, created_at in recent],
    )
