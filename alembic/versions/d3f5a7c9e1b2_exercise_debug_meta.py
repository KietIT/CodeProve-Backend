"""exercise debug metadata (P2.2: bug regions, explanation, hint)

Revision ID: d3f5a7c9e1b2
Revises: b4e6a8c0d2f1
Create Date: 2026-09-30 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d3f5a7c9e1b2"
down_revision: Union[str, None] = "b4e6a8c0d2f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("exercises", sa.Column("debug_meta", postgresql.JSONB().with_variant(sa.JSON(), "sqlite"),
                                         nullable=True))


def downgrade() -> None:
    op.drop_column("exercises", "debug_meta")
