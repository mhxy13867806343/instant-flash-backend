"""Add user new phone field."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0021_user_new_phone"
down_revision = "0020_admin_like_share_routes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("new_phone", sa.String(length=32), nullable=True))
    op.create_index(op.f("ix_users_new_phone"), "users", ["new_phone"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_users_new_phone"), table_name="users")
    op.drop_column("users", "new_phone")
