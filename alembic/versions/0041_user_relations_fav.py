"""create user_follows table and add category column to chat_message_favorites

Revision ID: 0041_user_relations_fav
Revises: 0040_user_third_party_bindings
Create Date: 2026-07-06 11:25:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0041_user_relations_fav"
down_revision = "0040_user_third_party_bindings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 创建 user_follows 表
    op.create_table(
        "user_follows",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("follow_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("following_id", sa.String(length=64), nullable=False),
        sa.Column("create_time", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("update_time", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["following_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "following_id", name="uq_user_follows_user_following"),
    )
    op.create_index("ix_user_follows_follow_id", "user_follows", ["follow_id"], unique=True)
    op.create_index("ix_user_follows_user_id", "user_follows", ["user_id"])
    op.create_index("ix_user_follows_following_id", "user_follows", ["following_id"])

    # 2. 为 chat_message_favorites 添加 category 列
    op.add_column(
        "chat_message_favorites",
        sa.Column("category", sa.String(length=32), nullable=False, server_default="text"),
    )


def downgrade() -> None:
    op.drop_column("chat_message_favorites", "category")
    op.drop_table("user_follows")
