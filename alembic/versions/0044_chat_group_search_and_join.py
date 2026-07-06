"""add region and join requests to chat groups

Revision ID: 0044_chat_group_search_and_join
Revises: 0043_mall_product_params
Create Date: 2026-07-06 12:40:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0044_chat_group_search_and_join"
down_revision = "0043_mall_product_params"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add region to chat_groups
    op.add_column("chat_groups", sa.Column("region", sa.String(length=128), nullable=True))
    op.create_index("ix_chat_groups_region", "chat_groups", ["region"])

    # 2. Create chat_group_join_requests table
    op.create_table(
        "chat_group_join_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column("group_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("create_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("update_time", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["group_id"], ["chat_groups.group_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
    )
    op.create_index("ix_chat_group_join_requests_request_id", "chat_group_join_requests", ["request_id"], unique=True)
    op.create_index("ix_chat_group_join_requests_group_id", "chat_group_join_requests", ["group_id"])
    op.create_index("ix_chat_group_join_requests_user_id", "chat_group_join_requests", ["user_id"])
    op.create_index("ix_chat_group_join_requests_status", "chat_group_join_requests", ["status"])


def downgrade() -> None:
    op.drop_index("ix_chat_group_join_requests_status", table_name="chat_group_join_requests")
    op.drop_index("ix_chat_group_join_requests_user_id", table_name="chat_group_join_requests")
    op.drop_index("ix_chat_group_join_requests_group_id", table_name="chat_group_join_requests")
    op.drop_index("ix_chat_group_join_requests_request_id", table_name="chat_group_join_requests")
    op.drop_table("chat_group_join_requests")

    op.drop_index("ix_chat_groups_region", table_name="chat_groups")
    op.drop_column("chat_groups", "region")
