"""A learner's plan and orders for administrators, and giving or ending a plan by hand."""
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.features.admin import service
from app.features.admin.router import Principal, ready_admin
from app.features.billing import service as billing
from app.models import User

router = APIRouter(prefix="/api/admin/users", tags=["admin billing"])


class AdminOrderOut(BaseModel):
    id: int
    plan_code: str
    amount: int
    status: str
    created_at: datetime
    paid_at: datetime | None
    provider_txn_id: int | None


class LearnerBillingOut(BaseModel):
    tier: str
    expires_at: datetime | None
    days_left: int
    orders: list[AdminOrderOut]


class _Reason(BaseModel):
    # Kept in the audit log, so every manual change says why it was made.
    reason: str = Field(min_length=3, max_length=200)

    @field_validator("reason")
    @classmethod
    def strip_reason(cls, value: str) -> str:
        value = " ".join(value.split())
        if len(value) < 3:
            raise ValueError("Reason is too short")
        return value


class GrantIn(_Reason):
    tier: Literal["plus", "pro"]
    days: int = Field(ge=1, le=366)


class RevokeIn(_Reason):
    pass


async def _learner(db: AsyncSession, user_id: int) -> User:
    user = (await db.execute(select(User).where(User.id == user_id, User.role == "user"))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


async def _state(db: AsyncSession, user_id: int) -> LearnerBillingOut:
    state = await billing.billing_state(db, user_id)
    return LearnerBillingOut(
        tier=state["tier"], expires_at=state["expires_at"], days_left=state["days_left"],
        orders=[AdminOrderOut.model_validate(order, from_attributes=True) for order in state["orders"]],
    )


@router.get("/{user_id}/billing", response_model=LearnerBillingOut)
async def learner_billing(
    user_id: int,
    response: Response,
    _principal: Principal = Depends(ready_admin),
    db: AsyncSession = Depends(get_db),
) -> LearnerBillingOut:
    response.headers["Cache-Control"] = "no-store"
    await _learner(db, user_id)
    return await _state(db, user_id)


@router.post("/{user_id}/subscription", response_model=LearnerBillingOut)
async def grant_subscription(
    user_id: int,
    data: GrantIn,
    request: Request,
    principal: Principal = Depends(ready_admin),
    db: AsyncSession = Depends(get_db),
) -> LearnerBillingOut:
    """Give a plan without payment. It replaces whatever plan is running and makes no order (no revenue)."""
    service.require_frontend_origin(request)
    learner = await _learner(db, user_id)
    await billing.grant_subscription(db, learner.id, data.tier, data.days)
    service.log(db, "subscription_granted", principal.user.id, learner.id, f"{data.tier} {data.days}d: {data.reason}")
    await db.commit()
    return await _state(db, learner.id)


@router.post("/{user_id}/subscription/revoke", response_model=LearnerBillingOut)
async def revoke_subscription(
    user_id: int,
    data: RevokeIn,
    request: Request,
    principal: Principal = Depends(ready_admin),
    db: AsyncSession = Depends(get_db),
) -> LearnerBillingOut:
    """End the running plan now. Refused when the learner is already on free."""
    service.require_frontend_origin(request)
    learner = await _learner(db, user_id)
    ended = await billing.revoke_subscription(db, learner.id)
    if ended is None:
        raise HTTPException(status_code=409, detail="This learner has no running plan")
    service.log(db, "subscription_revoked", principal.user.id, learner.id, f"{ended}: {data.reason}")
    await db.commit()
    return await _state(db, learner.id)
