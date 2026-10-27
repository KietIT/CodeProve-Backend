"""Bank transfers received through SePay, for administrators: a history list and chart-ready totals."""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.features.admin.router import Principal, ready_admin
from app.models import Order, PaymentEvent, User

router = APIRouter(prefix="/api/admin/payments", tags=["admin payments"])

# A transfer counts once SePay's call was signed correctly and the money came in (not out).
_incoming = (PaymentEvent.signature_valid.is_(True), PaymentEvent.raw["transferType"].as_string() == "in")


class PaymentOut(BaseModel):
    id: int
    received_at: datetime
    amount: int | None
    bank: str | None
    transfer_content: str | None
    provider_txn_id: int | None
    # Who paid, when the transfer carried one of our order codes. Both are None for a transfer we cannot match.
    order_id: int | None
    order_status: str | None
    plan_code: str | None
    user_id: int | None
    user_name: str | None
    user_email: str | None


class PaymentPage(BaseModel):
    items: list[PaymentOut]
    total: int
    limit: int
    offset: int


class DayPoint(BaseModel):
    date: str  # YYYY-MM-DD in quota_timezone
    revenue: int
    orders: int


class PlanSlice(BaseModel):
    plan_code: str
    revenue: int
    orders: int


class StatusSlice(BaseModel):
    status: str
    orders: int


class PaymentSummary(BaseModel):
    days: int
    revenue: int
    paid_orders: int
    average_order: int
    transfers_received: int
    # Money in that needs a person: paid while another plan ran, or a transfer matching no order / amount.
    needs_attention: int
    by_day: list[DayPoint]
    by_plan: list[PlanSlice]
    by_status: list[StatusSlice]


def _int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _text(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


@router.get("", response_model=PaymentPage)
async def payments(
    response: Response,
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    search: str | None = Query(None, max_length=100),
    _principal: Principal = Depends(ready_admin),
    db: AsyncSession = Depends(get_db),
) -> PaymentPage:
    """Incoming transfers, newest first, each with the learner it paid for (if any)."""
    response.headers["Cache-Control"] = "no-store"
    query = (
        select(PaymentEvent, Order, User)
        .outerjoin(Order, Order.id == PaymentEvent.order_id)
        .outerjoin(User, User.id == Order.user_id)
        .where(*_incoming)
    )
    term = (search or "").strip()
    if term:
        like = f"%{term.lower()}%"
        query = query.where(or_(func.lower(User.full_name).like(like), func.lower(User.email).like(like)))
    total = await db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = (await db.execute(
        query.order_by(PaymentEvent.received_at.desc(), PaymentEvent.id.desc()).limit(limit).offset(offset)
    )).all()
    items = [
        PaymentOut(
            id=event.id, received_at=event.received_at, amount=_int(event.raw.get("transferAmount")),
            bank=_text(event.raw.get("gateway")), transfer_content=_text(event.raw.get("content")),
            provider_txn_id=event.provider_txn_id, order_id=event.order_id,
            order_status=order.status if order else None, plan_code=order.plan_code if order else None,
            user_id=user.id if user else None, user_name=user.full_name if user else None,
            user_email=user.email if user else None,
        )
        for event, order, user in rows
    ]
    return PaymentPage(items=items, total=total, limit=limit, offset=offset)


@router.get("/summary", response_model=PaymentSummary)
async def summary(
    response: Response,
    days: int = Query(30, ge=1, le=365),
    _principal: Principal = Depends(ready_admin),
    db: AsyncSession = Depends(get_db),
) -> PaymentSummary:
    """Totals over the last `days` calendar days (quota_timezone), with a point for every day, even empty ones."""
    response.headers["Cache-Control"] = "no-store"
    zone = ZoneInfo(get_settings().quota_timezone)
    today = datetime.now(zone).date()
    first_day = today - timedelta(days=days - 1)
    since = datetime.combine(first_day, datetime.min.time(), tzinfo=zone).astimezone(timezone.utc)

    orders = (await db.execute(
        select(Order.plan_code, Order.amount, Order.paid_at, Order.status)
        .join(User, User.id == Order.user_id)
        .where(User.role == "user", Order.status.in_(("paid", "paid_unapplied")), Order.paid_at >= since)
    )).all()
    daily: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    plans: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for plan_code, amount, paid_at, _status in orders:
        if paid_at.tzinfo is None:  # SQLite hands back naive datetimes; they were stored as UTC
            paid_at = paid_at.replace(tzinfo=timezone.utc)
        day = paid_at.astimezone(zone).date().isoformat()
        daily[day][0] += amount
        daily[day][1] += 1
        plans[plan_code][0] += amount
        plans[plan_code][1] += 1
    by_day = [
        DayPoint(date=day.isoformat(), revenue=daily[day.isoformat()][0], orders=daily[day.isoformat()][1])
        for day in (first_day + timedelta(days=n) for n in range(days))
    ]
    revenue = sum(amount for _plan, amount, _paid, _status in orders)
    transfers = await db.scalar(select(func.count(PaymentEvent.id)).where(*_incoming, PaymentEvent.received_at >= since)) or 0
    # Incoming transfers that did not become a paid order: unmatched, wrong amount, or a repeat payment.
    unprocessed = await db.scalar(select(func.count(PaymentEvent.id)).where(
        *_incoming, PaymentEvent.received_at >= since, PaymentEvent.processed.is_(False))) or 0
    attention = unprocessed + sum(1 for _p, _a, _t, status in orders if status == "paid_unapplied")
    # Every order opened in the period by where it ended up (paid, still pending, expired...), for the donut chart.
    statuses = dict((await db.execute(
        select(Order.status, func.count(Order.id))
        .join(User, User.id == Order.user_id)
        .where(User.role == "user", Order.created_at >= since)
        .group_by(Order.status)
    )).all())
    return PaymentSummary(
        days=days, revenue=revenue, paid_orders=len(orders),
        average_order=revenue // len(orders) if orders else 0,
        transfers_received=transfers, needs_attention=attention,
        by_day=by_day,
        by_plan=[PlanSlice(plan_code=code, revenue=values[0], orders=values[1])
                 for code, values in sorted(plans.items(), key=lambda item: -item[1][0])],
        by_status=[StatusSlice(status=status, orders=count) for status, count in sorted(statuses.items())],
    )
