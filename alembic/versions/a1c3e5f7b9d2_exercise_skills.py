"""exercise skill tags (P3.2)

Revision ID: a1c3e5f7b9d2
Revises: e7a9c1d3f5b8
Create Date: 2026-09-30 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a1c3e5f7b9d2"
down_revision: Union[str, None] = "e7a9c1d3f5b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("exercises", sa.Column("skills", postgresql.JSONB().with_variant(sa.JSON(), "sqlite"),
                                         nullable=False, server_default="[]"))


def downgrade() -> None:
    op.drop_column("exercises", "skills")
