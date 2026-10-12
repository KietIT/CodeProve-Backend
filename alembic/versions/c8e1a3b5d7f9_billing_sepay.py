"""Billing: PayOS columns replaced by SePay ones.

Revision ID: c8e1a3b5d7f9
Revises: b6d8f0a2c4e7
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c8e1a3b5d7f9"
down_revision: Union[str, None] = "b6d8f0a2c4e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("provider_txn_id", sa.BigInteger(), nullable=True))
    op.drop_column("orders", "payos_order_code")
    op.drop_column("orders", "payment_link_id")
    op.drop_column("orders", "checkout_url")

    op.drop_index("ix_payment_events_payos_order_code", table_name="payment_events")
    op.drop_column("payment_events", "payos_order_code")
    op.add_column("payment_events", sa.Column("order_id", sa.Integer(), nullable=True))
    op.add_column("payment_events", sa.Column("provider_txn_id", sa.BigInteger(), nullable=True))
    op.create_index("ix_payment_events_order_id", "payment_events", ["order_id"])
    op.create_index("ix_payment_events_provider_txn_id", "payment_events", ["provider_txn_id"])


def downgrade() -> None:
    op.drop_index("ix_payment_events_provider_txn_id", table_name="payment_events")
    op.drop_index("ix_payment_events_order_id", table_name="payment_events")
    op.drop_column("payment_events", "provider_txn_id")
    op.drop_column("payment_events", "order_id")
    op.add_column("payment_events", sa.Column("payos_order_code", sa.BigInteger(), nullable=True))
    op.create_index("ix_payment_events_payos_order_code", "payment_events", ["payos_order_code"])

    # Old rows get their id as the order code so the NOT NULL + UNIQUE constraint can come back.
    op.add_column("orders", sa.Column("checkout_url", sa.String(512), nullable=True))
    op.add_column("orders", sa.Column("payment_link_id", sa.String(64), nullable=True))
    op.add_column("orders", sa.Column("payos_order_code", sa.BigInteger(), nullable=True))
    op.execute("UPDATE orders SET payos_order_code = id")
    op.alter_column("orders", "payos_order_code", nullable=False)
    op.create_unique_constraint("orders_payos_order_code_key", "orders", ["payos_order_code"])
    op.drop_column("orders", "provider_txn_id")
