"""test case categories and exercise mutant bank

Revision ID: b4e6a8c0d2f1
Revises: f2c4d6e8a1b3
Create Date: 2026-09-24 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "b4e6a8c0d2f1"
down_revision: Union[str, None] = "f2c4d6e8a1b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("test_cases", sa.Column("category", sa.String(length=16), nullable=True))
    op.create_table(
        "exercise_mutants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("exercise_id", sa.Integer(), sa.ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("bug_line", sa.Integer(), nullable=False),
        sa.Column("bug_type", sa.String(length=32), nullable=False),
        sa.Column("note_vi", sa.Text(), nullable=False, server_default=""),
        sa.Column("note_en", sa.Text(), nullable=False, server_default=""),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_exercise_mutants_exercise_id", "exercise_mutants", ["exercise_id"])


def downgrade() -> None:
    op.drop_index("ix_exercise_mutants_exercise_id", table_name="exercise_mutants")
    op.drop_table("exercise_mutants")
    op.drop_column("test_cases", "category")
