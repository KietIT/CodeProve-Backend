from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Subscription(Base):
    """A student's paid tier and when it ends. One row per user; no row or an expired row means free."""

    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    tier: Mapped[str] = mapped_column(String(16))  # plus | pro
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(),
                                                 onupdate=func.now())


class Order(Base):
    """One purchase of one plan period, paid by bank transfer. Only a verified webhook moves it to paid."""

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    plan_code: Mapped[str] = mapped_column(String(32))  # billing.plans.PLANS key
    amount: Mapped[int] = mapped_column(Integer)  # VND, from the server's price list at checkout time
    # pending | paid | paid_unapplied | cancelled | expired | refunded
    status: Mapped[str] = mapped_column(String(16), default="pending", server_default="pending", index=True)
    # SePay's id of the bank transaction that paid this order.
    provider_txn_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PaymentEvent(Base):
    """Every webhook SePay sent, as received, for reconciliation and to see replays. No card data."""

    __tablename__ = "payment_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)  # read from the content
    provider_txn_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    raw: Mapped[dict] = mapped_column(JSONB().with_variant(JSON, "sqlite"), default=dict)
    signature_valid: Mapped[bool] = mapped_column(Boolean, default=False)
    processed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
