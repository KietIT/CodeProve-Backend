import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import rate_limit
from app.core.config import get_settings
from app.core.db import get_db
from app.core.deps import get_current_user
from app.features.analytics import ga4
from app.features.billing import sepay_client, service
from app.features.billing.plans import PLANS
from app.models import Order, User
from app.schemas.billing import BillingMeOut, CheckoutIn, OrderOut, PaymentOut, PlanOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/billing", tags=["billing"])


@router.get("/plans", response_model=list[PlanOut])
async def plans() -> list[PlanOut]:
    return [PlanOut(**vars(p)) for p in PLANS.values()]


@router.get("/me", response_model=BillingMeOut)
async def me(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)) -> BillingMeOut:
    return BillingMeOut.model_validate(await service.billing_state(db, user.id))


@router.post("/checkout", response_model=PaymentOut)
async def checkout(data: CheckoutIn, db: AsyncSession = Depends(get_db),
                   user: User = Depends(get_current_user)) -> PaymentOut:
    rate_limit.enforce(f"checkout:{user.id}", get_settings().checkout_per_minute, 60)
    order = await service.create_checkout(db, user, data.plan_code, data.ga_client_id, data.ga_session_id)
    return PaymentOut(**service.payment_info(order))


@router.get("/orders/{order_id}/payment", response_model=PaymentOut)
async def payment(order_id: int, db: AsyncSession = Depends(get_db),
                  user: User = Depends(get_current_user)) -> PaymentOut:
    """The transfer details of one of the student's orders (the payment page reloads from this)."""
    return PaymentOut(**service.payment_info(await service.get_order(db, user, order_id)))


@router.post("/orders/{order_id}/cancel", response_model=OrderOut)
async def cancel(order_id: int, db: AsyncSession = Depends(get_db),
                 user: User = Depends(get_current_user)) -> OrderOut:
    return OrderOut.model_validate(await service.cancel_order(db, user, order_id))


@router.post("/webhook")
async def webhook(request: Request, background: BackgroundTasks, db: AsyncSession = Depends(get_db)) -> dict:
    """Called by SePay, not by the browser. Trusted only when it carries our API key."""
    try:
        body = await request.json()
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON")
    if not isinstance(body, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payload")
    outcome = await service.handle_webhook(db, body, request.headers.get("authorization"))
    if outcome == "invalid_signature":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    logger.info("SePay webhook: %s", outcome)
    if outcome == "activated" and ga4.configured():
        order = await db.get(Order, sepay_client.order_id_from(body))
        if order is not None:  # reported after SePay has its answer; a GA failure is only logged
            background.add_task(ga4.send_purchase, ga4.purchase_payload(order))
    return {"success": True}
