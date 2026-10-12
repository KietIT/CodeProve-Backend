"""SePay: bank-transfer payments confirmed by webhook.

There is no payment link to create. The student transfers the order's amount to our bank account with the
order's payment code as the transfer content (the QR fills both in); SePay sees the transfer on the account and
calls our webhook (https://docs.sepay.vn/tich-hop-webhooks.html). The webhook is trusted by its API key header.
"""
import hmac
import re
from urllib.parse import urlencode

from app.core.config import get_settings


def configured() -> bool:
    s = get_settings()
    return bool(s.sepay_api_key and s.sepay_bank_account and s.sepay_bank_name)


def verify_webhook(authorization: str | None, key: str | None = None) -> bool:
    """True when the `Authorization` header is `Apikey <our key>`. Constant-time; False when no key is set."""
    key = key if key is not None else get_settings().sepay_api_key
    if not key or not isinstance(authorization, str):
        return False
    scheme, _, value = authorization.strip().partition(" ")
    return scheme.lower() == "apikey" and hmac.compare_digest(value.strip().encode(), key.encode())


def payment_code(order_id: int) -> str:
    """The transfer content that identifies an order, e.g. "CP12"."""
    return f"{get_settings().sepay_code_prefix}{order_id}"


def order_id_from(body: dict) -> int | None:
    """The order a transfer pays for, read from SePay's detected `code` or else from the transfer content.

    Banks wrap the content in their own text ("MBVCB.123.CP12.CT tu ..."), so the code is searched for.
    """
    pattern = re.compile(rf"{re.escape(get_settings().sepay_code_prefix)}(\d{{1,12}})(?!\d)", re.IGNORECASE)
    for field in ("code", "content"):
        value = body.get(field)
        match = pattern.search(value) if isinstance(value, str) else None
        if match:
            return int(match.group(1))
    return None


def payment_details(order_id: int, amount: int) -> dict:
    """What the student needs to pay an order: the account, the exact amount, the content, and a VietQR image."""
    s = get_settings()
    code = payment_code(order_id)
    query = urlencode({"acc": s.sepay_bank_account, "bank": s.sepay_bank_name, "amount": amount, "des": code})
    return {
        "bank_name": s.sepay_bank_name,
        "account_number": s.sepay_bank_account,
        "account_name": s.sepay_account_name,
        "amount": amount,
        "payment_code": code,
        "qr_url": f"{s.sepay_qr_url}?{query}",
    }
