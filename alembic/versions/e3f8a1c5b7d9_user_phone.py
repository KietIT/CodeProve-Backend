"""Add a unique Vietnamese phone number to users (signup requirement, login ID).

Revision ID: e3f8a1c5b7d9
Revises: b9e4a7c2d610
"""
from alembic import op
import sqlalchemy as sa

revision = "e3f8a1c5b7d9"
down_revision = "b9e4a7c2d610"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Nullable: existing accounts and Google sign-ins have no phone yet.
    op.add_column("users", sa.Column("phone", sa.String(length=16), nullable=True))
    op.create_index("ix_users_phone", "users", ["phone"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_phone", table_name="users")
    op.drop_column("users", "phone")
