import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

_GA_CLIENT_ID = re.compile(r"^\d{1,20}\.\d{1,20}$")


class PlanOut(BaseModel):
    code: str
    tier: str
    period: str
    amount: int
    days: int


class EntitlementsOut(BaseModel):
    tier: str
    ciel_per_day: int
    monthly_submits: int | None
    detailed_analysis: bool
    learning_path: bool


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plan_code: str
    amount: int
    status: str
    created_at: datetime
    paid_at: datetime | None


class BillingMeOut(BaseModel):
    tier: str
    expires_at: datetime | None
    days_left: int
    entitlements: EntitlementsOut
    orders: list[OrderOut]


class CheckoutIn(BaseModel):
    plan_code: str
    # From gtag('get', <measurement id>, 'client_id' / 'session_id'). Optional: blocked or missing analytics
    # must never stop a purchase, so a malformed value is dropped instead of rejected.
    ga_client_id: str | None = None
    ga_session_id: int | None = None

    @field_validator("ga_client_id", mode="before")
    @classmethod
    def _client_id(cls, v: object) -> str | None:
        return v if isinstance(v, str) and _GA_CLIENT_ID.match(v) else None

    @field_validator("ga_session_id", mode="before")
    @classmethod
    def _session_id(cls, v: object) -> int | None:
        if isinstance(v, str) and v.isdigit() and len(v) <= 15:
            v = int(v)
        return v if isinstance(v, int) and not isinstance(v, bool) and 0 < v < 10**15 else None


class PaymentOut(BaseModel):
    """How to pay a pending order by bank transfer. The transfer content must be exactly `payment_code`."""

    order_id: int
    status: str
    plan_code: str
    amount: int
    payment_code: str
    bank_name: str
    account_number: str
    account_name: str
    qr_url: str
    expires_at: datetime
