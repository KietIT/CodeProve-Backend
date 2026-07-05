"""add daily bug hunt tables

Revision ID: e5a91f3d7c22
Revises: c8d4e2b7f1a0
Create Date: 2026-07-04 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "e5a91f3d7c22"
down_revision: Union[str, None] = "c8d4e2b7f1a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "daily_challenges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("challenge_date", sa.Date(), nullable=False, unique=True),
        sa.Column("prompt_title", sa.String(length=255), nullable=False),
        sa.Column("buggy_code", sa.Text(), nullable=False),
        sa.Column("buggy_line", sa.Integer(), nullable=False),
        sa.Column("bug_category", sa.String(length=64), nullable=False),
        sa.Column("hint_1", sa.Text(), nullable=False),
        sa.Column("hint_2", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_daily_challenges_challenge_date", "daily_challenges", ["challenge_date"])

    op.create_table(
        "daily_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("challenge_date", sa.Date(), nullable=False),
        sa.Column("selected_line", sa.Integer(), nullable=True),
        sa.Column("hints_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("time_taken_seconds", sa.Integer(), nullable=True),
        sa.Column("tier", sa.String(length=16), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "challenge_date", name="uq_daily_attempt_user_date"),
    )
    op.create_index("ix_daily_attempts_user_id", "daily_attempts", ["user_id"])
    op.create_index("ix_daily_attempts_challenge_date", "daily_attempts", ["challenge_date"])


def downgrade() -> None:
    op.drop_index("ix_daily_attempts_challenge_date", table_name="daily_attempts")
    op.drop_index("ix_daily_attempts_user_id", table_name="daily_attempts")
    op.drop_table("daily_attempts")
    op.drop_index("ix_daily_challenges_challenge_date", table_name="daily_challenges")
    op.drop_table("daily_challenges")
