"""bilingual daily challenge content

Revision ID: a7d24c8e9b31
Revises: e5a91f3d7c22
Create Date: 2026-07-06 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a7d24c8e9b31"
down_revision: Union[str, None] = "e5a91f3d7c22"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The feature is unreleased: existing rows are dev-only generated content
    # whose missing-language halves cannot be backfilled, so wipe them (and
    # the attempts that reference those challenge dates) instead of trying.
    op.execute("DELETE FROM daily_attempts")
    op.execute("DELETE FROM daily_challenges")

    op.drop_column("daily_challenges", "prompt_title")
    op.drop_column("daily_challenges", "hint_1")
    op.drop_column("daily_challenges", "hint_2")
    op.drop_column("daily_challenges", "explanation")

    # Tables are empty (deleted above), so non-null columns need no default.
    op.add_column("daily_challenges", sa.Column("prompt_title_vi", sa.String(length=255), nullable=False))
    op.add_column("daily_challenges", sa.Column("prompt_title_en", sa.String(length=255), nullable=False))
    op.add_column("daily_challenges", sa.Column("hint_1_vi", sa.Text(), nullable=False))
    op.add_column("daily_challenges", sa.Column("hint_1_en", sa.Text(), nullable=False))
    op.add_column("daily_challenges", sa.Column("hint_2_vi", sa.Text(), nullable=False))
    op.add_column("daily_challenges", sa.Column("hint_2_en", sa.Text(), nullable=False))
    op.add_column("daily_challenges", sa.Column("explanation_vi", sa.Text(), nullable=False))
    op.add_column("daily_challenges", sa.Column("explanation_en", sa.Text(), nullable=False))


def downgrade() -> None:
    op.execute("DELETE FROM daily_attempts")
    op.execute("DELETE FROM daily_challenges")

    op.drop_column("daily_challenges", "explanation_en")
    op.drop_column("daily_challenges", "explanation_vi")
    op.drop_column("daily_challenges", "hint_2_en")
    op.drop_column("daily_challenges", "hint_2_vi")
    op.drop_column("daily_challenges", "hint_1_en")
    op.drop_column("daily_challenges", "hint_1_vi")
    op.drop_column("daily_challenges", "prompt_title_en")
    op.drop_column("daily_challenges", "prompt_title_vi")

    op.add_column("daily_challenges", sa.Column("prompt_title", sa.String(length=255), nullable=False))
    op.add_column("daily_challenges", sa.Column("hint_1", sa.Text(), nullable=False))
    op.add_column("daily_challenges", sa.Column("hint_2", sa.Text(), nullable=False))
    op.add_column("daily_challenges", sa.Column("explanation", sa.Text(), nullable=False))
