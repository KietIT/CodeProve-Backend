import logging
import math
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.features.billing import sepay_client
from app.features.billing.entitlements import Entitlements, for_tier
from app.features.billing.plans import FREE, PLANS
from app.models import Order, PaymentEvent, Subscription, User

logger = logging.getLogger(__name__)


def _utc(moment: datetime) -> datetime:
    # SQLite gives naive datetimes (stored as UTC); Postgres gives aware ones.
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def _error(code: int, name: str, message_vi: str, message_en: str, **extra) -> HTTPException:
    return HTTPException(status_code=code, detail={"code": name, "message_vi": message_vi,
                                                   "message_en": message_en, **extra})


async def active_subscription(db: AsyncSession, user_id: int, now: datetime | None = None) -> Subscription | None:
    """The user's subscription if it has not expired yet."""
    now = now or datetime.now(timezone.utc)
    sub = (await db.execute(select(Subscription).where(Subscription.user_id == user_id))).scalar_one_or_none()
    return sub if sub is not None and _utc(sub.expires_at) > now else None


async def current_tier(db: AsyncSession, user_id: int) -> str:
    sub = await active_subscription(db, user_id)
    return sub.tier if sub is not None else FREE


async def entitlements_for(db: AsyncSession, user_id: int) -> Entitlements:
    return for_tier(await current_tier(db, user_id))


async def expire_stale_orders(db: AsyncSession, user_id: int, now: datetime | None = None) -> None:
    """Pending orders past the payment window become expired. Done when read, so no scheduler is needed."""
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(minutes=get_settings().payment_window_minutes)
    await db.execute(update(Order).where(Order.user_id == user_id, Order.status == "pending",
                                         Order.created_at < cutoff).values(status="expired")
                     .execution_options(synchronize_session="fetch"))


async def billing_state(db: AsyncSession, user_id: int, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    await expire_stale_orders(db, user_id, now)
    await db.commit()
    sub = await active_subscription(db, user_id, now)
    tier = sub.tier if sub is not None else FREE
    days_left = math.ceil((_utc(sub.expires_at) - now).total_seconds() / 86400) if sub is not None else 0
    orders = (await db.execute(
        select(Order).where(Order.user_id == user_id).order_by(Order.created_at.desc(), Order.id.desc()).limit(50)
    )).scalars().all()
    return {
        "tier": tier,
        "expires_at": sub.expires_at if sub is not None else None,
        "days_left": days_left,
        "entitlements": asdict(for_tier(tier)),
        "orders": orders,
    }


def payment_info(order: Order) -> dict:
    """An order with the bank-transfer details that pay it."""
    return {
        "order_id": order.id, "status": order.status, "plan_code": order.plan_code,
        "expires_at": _utc(order.created_at) + timedelta(minutes=get_settings().payment_window_minutes),
        **sepay_client.payment_details(order.id, order.amount),
    }


async def get_order(db: AsyncSession, user: User, order_id: int) -> Order:
    await expire_stale_orders(db, user.id)
    await db.commit()
    order = (await db.execute(select(Order).where(Order.id == order_id, Order.user_id == user.id))
             ).scalar_one_or_none()
    if order is None:
        raise _error(status.HTTP_404_NOT_FOUND, "order_not_found", "Không tìm thấy đơn hàng.", "Order not found.")
    return order


async def create_checkout(db: AsyncSession, user: User, plan_code: str, ga_client_id: str | None = None,
                          ga_session_id: int | None = None) -> Order:
    """A pending order to pay by bank transfer. The plan starts only when the webhook confirms the money.

    The GA4 ids (optional) let the paid webhook report the purchase to the visit that brought the buyer."""
    plan = PLANS.get(plan_code)
    if plan is None:
        raise _error(status.HTTP_404_NOT_FOUND, "unknown_plan", "Gói không tồn tại.", "Unknown plan.")
    if not sepay_client.configured():
        raise _error(status.HTTP_503_SERVICE_UNAVAILABLE, "payments_not_configured",
                     "Thanh toán chưa được bật.", "Payments are not enabled.")
    now = datetime.now(timezone.utc)
    sub = await active_subscription(db, user.id, now)
    if sub is not None and sub.tier != plan.tier:
        # No switching mid-term: Plus runs out first, then Pro can be bought (and the other way round).
        raise _error(status.HTTP_409_CONFLICT, "plan_change_not_allowed",
                     "Bạn đang dùng một gói khác. Hãy đợi gói hiện tại hết hạn rồi đăng ký gói mới.",
                     "You have another plan running. Wait for it to expire before buying a different one.",
                     current_tier=sub.tier, expires_at=_utc(sub.expires_at).isoformat())

    await expire_stale_orders(db, user.id, now)
    reusable = (await db.execute(select(Order).where(
        Order.user_id == user.id, Order.status == "pending", Order.plan_code == plan.code)
        .order_by(Order.id.desc()))).scalars().first()
    if reusable is not None:
        if ga_client_id:  # the latest visit is the one that should get the credit
            reusable.ga_client_id, reusable.ga_session_id = ga_client_id, ga_session_id
        await db.commit()
        return reusable

    order = Order(user_id=user.id, plan_code=plan.code, amount=plan.amount, status="pending",
                  ga_client_id=ga_client_id, ga_session_id=ga_session_id)
    db.add(order)
    await db.commit()
    await db.refresh(order)
    return order


async def cancel_order(db: AsyncSession, user: User, order_id: int) -> Order:
    order = (await db.execute(select(Order).where(Order.id == order_id, Order.user_id == user.id)
                              .with_for_update())).scalar_one_or_none()
    if order is None:
        raise _error(status.HTTP_404_NOT_FOUND, "order_not_found", "Không tìm thấy đơn hàng.", "Order not found.")
    if order.status != "pending":
        raise _error(status.HTTP_409_CONFLICT, "order_not_pending", "Đơn hàng không còn chờ thanh toán.",
                     "This order is no longer waiting for payment.")
    order.status = "cancelled"
    await db.commit()
    await db.refresh(order)
    return order


async def grant_subscription(db: AsyncSession, user_id: int, tier: str, days: int) -> Subscription:
    """Give a plan without payment: `tier` for `days` from now, replacing whatever plan was running.

    The caller commits (and records who did it).
    """
    expires = datetime.now(timezone.utc) + timedelta(days=days)
    sub = (await db.execute(select(Subscription).where(Subscription.user_id == user_id)
                            .with_for_update())).scalar_one_or_none()
    if sub is None:
        sub = Subscription(user_id=user_id, tier=tier, expires_at=expires)
        db.add(sub)
    else:
        sub.tier, sub.expires_at = tier, expires
    return sub


async def revoke_subscription(db: AsyncSession, user_id: int) -> str | None:
    """End the running plan now. Returns the tier that was ended, or None when there was nothing to end.

    The caller commits.
    """
    now = datetime.now(timezone.utc)
    sub = (await db.execute(select(Subscription).where(Subscription.user_id == user_id)
                            .with_for_update())).scalar_one_or_none()
    if sub is None or _utc(sub.expires_at) <= now:
        return None
    sub.expires_at = now
    return sub.tier


def _apply_paid_order(sub: Subscription | None, user_id: int, tier: str, days: int, now: datetime):
    """The subscription after a paid order: same tier still running -> extended, otherwise starts now."""
    if sub is None:
        return Subscription(user_id=user_id, tier=tier, expires_at=now + timedelta(days=days))
    if _utc(sub.expires_at) > now and sub.tier == tier:
        sub.expires_at = _utc(sub.expires_at) + timedelta(days=days)
    else:
        sub.tier = tier
        sub.expires_at = now + timedelta(days=days)
    return sub


async def handle_webhook(db: AsyncSession, body: dict, authorization: str | None) -> str:
    """Record a SePay webhook and, if it is a trusted incoming transfer for one of our orders, activate the plan.

    Returns what happened: "invalid_signature" (wrong or missing API key: nothing is applied), "ignored" (not
    an incoming transfer, or no order of ours in the content), "duplicate" (already applied), "amount_mismatch",
    "unapplied" (paid while another tier was running: needs a person), or "activated". Safe to call again
    with the same body.
    """
    valid = sepay_client.verify_webhook(authorization)
    txn_id = body.get("id") if isinstance(body.get("id"), int) else None
    order_id = sepay_client.order_id_from(body)
    event = PaymentEvent(order_id=order_id, provider_txn_id=txn_id, raw=body, signature_valid=valid)
    db.add(event)
    if not valid:
        await db.commit()
        return "invalid_signature"
    if body.get("transferType") != "in" or order_id is None:
        await db.commit()
        return "ignored"  # money going out, or a transfer that is not for an order

    order = (await db.execute(select(Order).where(Order.id == order_id).with_for_update())).scalar_one_or_none()
    if order is None:
        await db.commit()
        return "ignored"
    if order.status in ("paid", "paid_unapplied", "refunded"):
        # A resend of the same transfer, or a second transfer with the same content (kept in payment_events).
        event.processed = order.provider_txn_id == txn_id
        if not event.processed:
            logger.warning("Order %s is already paid; extra transfer %s was not applied", order.id, txn_id)
        await db.commit()
        return "duplicate"
    if body.get("transferAmount") != order.amount:
        logger.warning("SePay amount mismatch for order %s: got %r, expected %s",
                       order.id, body.get("transferAmount"), order.amount)
        await db.commit()
        return "amount_mismatch"

    plan = PLANS[order.plan_code]
    now = datetime.now(timezone.utc)
    sub = (await db.execute(select(Subscription).where(Subscription.user_id == order.user_id)
                            .with_for_update())).scalar_one_or_none()
    order.paid_at = now
    order.provider_txn_id = txn_id
    event.processed = True
    if sub is not None and _utc(sub.expires_at) > now and sub.tier != plan.tier:
        # Money arrived for a different tier than the one running (two orders opened before paying).
        # Do not change the subscription; support resolves it (refund or grant later).
        order.status = "paid_unapplied"
        logger.warning("Order %s paid while tier %s is active; not applied", order.id, sub.tier)
        await db.commit()
        return "unapplied"
    order.status = "paid"
    db.add(_apply_paid_order(sub, order.user_id, plan.tier, plan.days, now))
    await db.commit()
    return "activated"
