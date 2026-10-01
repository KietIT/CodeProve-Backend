"""Admin exercise drafts and exercise audit target.

Revision ID: a9b4c6d8e210
Revises: f6a3c9d2e410
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "a9b4c6d8e210"
down_revision: Union[str, None] = "f6a3c9d2e410"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("exercises", sa.Column("content_source", sa.String(16), nullable=False, server_default="file"))
    op.add_column("admin_audit_logs", sa.Column("target_exercise_code", sa.String(32), nullable=True))
    op.create_index("ix_admin_audit_logs_target_exercise_code", "admin_audit_logs", ["target_exercise_code"])
    op.create_table(
        "exercise_drafts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("payload", sa.JSON().with_variant(JSONB(), "postgresql"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("author_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewer_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_exercise_drafts_code", "exercise_drafts", ["code"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_exercise_drafts_code", table_name="exercise_drafts")
    op.drop_table("exercise_drafts")
    op.drop_index("ix_admin_audit_logs_target_exercise_code", table_name="admin_audit_logs")
    op.drop_column("admin_audit_logs", "target_exercise_code")
    op.drop_column("exercises", "content_source")
