from datetime import datetime

from pydantic import BaseModel, ConfigDict


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
