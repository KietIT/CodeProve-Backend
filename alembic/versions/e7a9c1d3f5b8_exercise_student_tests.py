"""exercise student tests flag (P2.3: the Tests tab)

Revision ID: e7a9c1d3f5b8
Revises: d3f5a7c9e1b2
Create Date: 2026-09-30 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "e7a9c1d3f5b8"
down_revision: Union[str, None] = "d3f5a7c9e1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("exercises", sa.Column("student_tests", sa.Boolean(), nullable=False,
                                         server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("exercises", "student_tests")
