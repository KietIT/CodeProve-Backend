"""learner model: Elo per skill and exercise difficulty (P3.3)

Revision ID: b3d5f7a9c1e4
Revises: a1c3e5f7b9d2
Create Date: 2026-09-30 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "b3d5f7a9c1e4"
down_revision: Union[str, None] = "a1c3e5f7b9d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "learner_skills",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("skill", sa.String(length=40), nullable=False),
        sa.Column("rating", sa.Float(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "skill", name="uq_learner_skill_user_skill"),
    )
    op.create_index("ix_learner_skills_user_id", "learner_skills", ["user_id"])
    op.add_column("exercises", sa.Column("difficulty_elo", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("exercises", "difficulty_elo")
    op.drop_index("ix_learner_skills_user_id", table_name="learner_skills")
    op.drop_table("learner_skills")
