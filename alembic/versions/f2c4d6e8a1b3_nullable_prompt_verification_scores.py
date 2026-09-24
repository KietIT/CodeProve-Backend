"""prompt/verification scores nullable (axis may be not applicable)

Revision ID: f2c4d6e8a1b3
Revises: a7d24c8e9b31
Create Date: 2026-09-24 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "f2c4d6e8a1b3"
down_revision: Union[str, None] = "a7d24c8e9b31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("fluency_reports", "prompt_score", existing_type=sa.Float(), nullable=True)
    op.alter_column("fluency_reports", "verification_score", existing_type=sa.Float(), nullable=True)


def downgrade() -> None:
    # N/A cannot be represented once the columns are NOT NULL again: store 0.
    op.execute("UPDATE fluency_reports SET prompt_score = 0 WHERE prompt_score IS NULL")
    op.execute("UPDATE fluency_reports SET verification_score = 0 WHERE verification_score IS NULL")
    op.alter_column("fluency_reports", "prompt_score", existing_type=sa.Float(), nullable=False)
    op.alter_column("fluency_reports", "verification_score", existing_type=sa.Float(), nullable=False)
