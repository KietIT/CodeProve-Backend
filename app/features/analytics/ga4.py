"""Google Analytics 4 events the server reports itself (Measurement Protocol).

The browser sends page views and sign_up. A purchase is reported from here because the money arrives by bank
transfer, often after the buyer has closed the payment page: only the SePay webhook knows it was paid.
The buyer's GA ids are saved on the order at checkout, so GA credits the visit (TikTok, Facebook...) that
brought them. https://developers.google.com/analytics/devguides/collection/protocol/ga4
"""
import logging
from datetime import datetime, timezone

import httpx

from app.core.config import get_settings
from app.features.billing import sepay_client
from app.features.billing.plans import PLANS
from app.models import Order

logger = logging.getLogger(__name__)

_COLLECT_URL = "https://www.google-analytics.com/mp/collect"


def configured() -> bool:
    s = get_settings()
    return bool(s.ga_measurement_id and s.ga_api_secret)


def purchase_payload(order: Order) -> dict:
    """The Measurement Protocol body for a paid order. No name or email: GA only gets the order and plan."""
    plan = PLANS[order.plan_code]
    paid_at = order.paid_at or datetime.now(timezone.utc)
    if paid_at.tzinfo is None:
        paid_at = paid_at.replace(tzinfo=timezone.utc)
    params: dict = {
        # The payment code, so GA drops a repeat of the same purchase and it can be matched to the bank line.
        "transaction_id": sepay_client.payment_code(order.id),
        "value": order.amount,
        "currency": "VND",
        "engagement_time_msec": 1,
        "items": [{"item_id": plan.code, "item_name": plan.tier.capitalize(), "item_variant": plan.period,
                   "price": order.amount, "quantity": 1}],
    }
    if order.ga_session_id:
        params["session_id"] = order.ga_session_id
    return {
        # Without the browser's id (analytics blocked) the purchase still counts, under source "(not set)".
        "client_id": order.ga_client_id or f"server.{order.user_id}",
        "timestamp_micros": int(paid_at.timestamp() * 1_000_000),
        "non_personalized_ads": True,
        "events": [{"name": "purchase", "params": params}],
    }


async def send_purchase(payload: dict) -> bool:
    """Post one purchase to GA4. Never raises: analytics must not affect payments. False when not sent."""
    s = get_settings()
    if not configured():
        return False
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(_COLLECT_URL, json=payload,
                                     params={"measurement_id": s.ga_measurement_id, "api_secret": s.ga_api_secret})
    except httpx.HTTPError as exc:
        logger.warning("GA4 purchase %s not sent: %s", payload["events"][0]["params"]["transaction_id"], exc)
        return False
    if resp.status_code >= 300:
        logger.warning("GA4 purchase %s rejected: HTTP %s", payload["events"][0]["params"]["transaction_id"],
                       resp.status_code)
        return False
    return True
