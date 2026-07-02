"""add exercise kind

Revision ID: c8d4e2b7f1a0
Revises: b7e2f1a9c3d4
Create Date: 2026-07-02 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "c8d4e2b7f1a0"
down_revision: Union[str, None] = "b7e2f1a9c3d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Exercises whose task is to find/fix a flaw in the shown code: their buggy
# starter must be displayed verbatim, never stripped to a stub.
DEBUG_EXERCISE_CODES = (
    "CP-004", "CP-008", "CP-012", "CP-102", "CP-106",
    "CP-109", "CP-203", "CP-206", "CP-208",
)


def upgrade() -> None:
    op.add_column(
        "exercises",
        sa.Column("kind", sa.String(length=16), nullable=False, server_default="implement"),
    )
    codes = ", ".join(f"'{c}'" for c in DEBUG_EXERCISE_CODES)
    op.execute(f"UPDATE exercises SET kind = 'debug' WHERE code IN ({codes})")


def downgrade() -> None:
    op.drop_column("exercises", "kind")
