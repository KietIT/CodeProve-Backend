"""Orders remember the buyer's GA4 client and session ids, so the paid webhook can report the purchase.

Revision ID: d9b2f4a6c8e1
Revises: c8e1a3b5d7f9
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d9b2f4a6c8e1"
down_revision: Union[str, None] = "c8e1a3b5d7f9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("ga_client_id", sa.String(64), nullable=True))
    op.add_column("orders", sa.Column("ga_session_id", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "ga_session_id")
    op.drop_column("orders", "ga_client_id")
