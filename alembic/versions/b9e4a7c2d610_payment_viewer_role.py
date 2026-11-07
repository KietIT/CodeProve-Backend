"""Allow payment-only staff without granting administrator access.

Revision ID: b9e4a7c2d610
Revises: d9b2f4a6c8e1
"""
from alembic import op
import sqlalchemy as sa

revision = "b9e4a7c2d610"
down_revision = "d9b2f4a6c8e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.create_check_constraint("ck_users_role", "users",
                               "role IN ('user', 'admin', 'super_admin', 'payment_viewer')")


def downgrade() -> None:
    # Keep accounts and their audit history, but disable them before removing the role.
    op.execute(sa.text("UPDATE users SET is_active = false, role = 'user' WHERE role = 'payment_viewer'"))
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.create_check_constraint("ck_users_role", "users", "role IN ('user', 'admin', 'super_admin')")
