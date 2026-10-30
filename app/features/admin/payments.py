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

# The account also receives money unrelated to CodeProve. A transfer counts only when SePay's call was signed
# correctly, the money came in, and its content carries the code of one of our orders (joined as an order below).
_incoming = (PaymentEvent.signature_valid.is_(True), PaymentEvent.raw["transferType"].as_string() == "in",
             PaymentEvent.order_id.is_not(None))


class PaymentOut(BaseModel):
    id: int
    received_at: datetime
    amount: int | None
    bank: str | None
    transfer_content: str | None
    provider_txn_id: int | None
    # From SePay's webhook: the receiving account, the bank's own reference and the bank's time ("YYYY-MM-DD
    # HH:MM:SS", Vietnam time). The payer's own account number is not sent; the content often names the payer.
    account_number: str | None
    reference_code: str | None
    transaction_date: str | None
    order_id: int
    order_status: str
    plan_code: str
    user_id: int
    user_name: str
    user_email: str


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
    """Incoming transfers that paid a CodeProve order, newest first, each with the learner it was for."""
    response.headers["Cache-Control"] = "no-store"
    query = (
        select(PaymentEvent, Order, User)
        .join(Order, Order.id == PaymentEvent.order_id)
        .join(User, User.id == Order.user_id)
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
            provider_txn_id=event.provider_txn_id, account_number=_text(event.raw.get("accountNumber")),
            reference_code=_text(event.raw.get("referenceCode")),
            transaction_date=_text(event.raw.get("transactionDate")), order_id=order.id,
            order_status=order.status, plan_code=order.plan_code,
            user_id=user.id, user_name=user.full_name, user_email=user.email,
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
    transfers = await db.scalar(
        select(func.count(PaymentEvent.id)).join(Order, Order.id == PaymentEvent.order_id)
        .where(*_incoming, PaymentEvent.received_at >= since)) or 0
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
        transfers_received=transfers,
        by_day=by_day,
        by_plan=[PlanSlice(plan_code=code, revenue=values[0], orders=values[1])
                 for code, values in sorted(plans.items(), key=lambda item: -item[1][0])],
        by_status=[StatusSlice(status=status, orders=count) for status, count in sorted(statuses.items())],
    )
