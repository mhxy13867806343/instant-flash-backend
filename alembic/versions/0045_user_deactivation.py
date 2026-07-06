"""add deactivation columns to users table

Revision ID: 0045_user_deactivation
Revises: 0044_chat_group_search_and_join
Create Date: 2026-07-06 12:45:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0045_user_deactivation"
down_revision = "0044_chat_group_search_and_join"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("deactivation_status", sa.String(length=32), nullable=True))
    op.add_column("users", sa.Column("deactivation_reason", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("deactivation_apply_time", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("deactivation_end_time", sa.DateTime(timezone=True), nullable=True))

    op.create_index("ix_users_deactivation_status", "users", ["deactivation_status"])


def downgrade() -> None:
    op.drop_index("ix_users_deactivation_status", table_name="users")

    op.drop_column("users", "deactivation_end_time")
    op.drop_column("users", "deactivation_apply_time")
    op.drop_column("users", "deactivation_reason")
    op.drop_column("users", "deactivation_status")
