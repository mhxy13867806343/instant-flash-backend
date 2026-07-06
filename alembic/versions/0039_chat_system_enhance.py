"""enhance chat system with group chat and message operations

Revision ID: 0039_chat_system_enhance
Revises: 0038_wallet_pay_method
Create Date: 2026-07-06 09:30:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0039_chat_system_enhance"
down_revision = "0038_wallet_pay_method"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 增强 global_chat_messages 表，新增媒体和操作字段
    op.add_column("global_chat_messages", sa.Column("media_url", sa.String(length=512), nullable=True))
    op.add_column("global_chat_messages", sa.Column("thumbnail_url", sa.String(length=512), nullable=True))
    op.add_column("global_chat_messages", sa.Column("file_name", sa.String(length=256), nullable=True))
    op.add_column("global_chat_messages", sa.Column("file_size", sa.Integer(), nullable=True))
    op.add_column("global_chat_messages", sa.Column("duration", sa.Integer(), nullable=True))
    op.add_column("global_chat_messages", sa.Column("reply_to_id", sa.String(length=64), nullable=True))
    op.add_column("global_chat_messages", sa.Column("forward_from_id", sa.String(length=64), nullable=True))
    op.add_column("global_chat_messages", sa.Column("is_recalled", sa.Boolean(), server_default=sa.text("false"), nullable=False))

    # 2. 群聊表
    op.create_table(
        "chat_groups",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("group_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("avatar", sa.String(length=512), nullable=True),
        sa.Column("owner_id", sa.String(length=64), nullable=False),
        sa.Column("announcement", sa.Text(), nullable=True),
        sa.Column("max_members", sa.Integer(), server_default=sa.text("200"), nullable=False),
        sa.Column("member_count", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("is_muted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("last_message", sa.Text(), nullable=True),
        sa.Column("last_message_time", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'active'"), nullable=False),
        sa.Column("create_time", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("update_time", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chat_groups_group_id", "chat_groups", ["group_id"], unique=True)
    op.create_index("ix_chat_groups_owner_id", "chat_groups", ["owner_id"])
    op.create_index("ix_chat_groups_status", "chat_groups", ["status"])

    # 3. 群成员表
    op.create_table(
        "chat_group_members",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("group_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("role", sa.String(length=32), server_default=sa.text("'member'"), nullable=False),
        sa.Column("nickname_in_group", sa.String(length=64), nullable=True),
        sa.Column("is_muted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("create_time", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("update_time", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["chat_groups.group_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("group_id", "user_id", name="uq_chat_group_members_group_user"),
    )
    op.create_index("ix_chat_group_members_group_id", "chat_group_members", ["group_id"])
    op.create_index("ix_chat_group_members_user_id", "chat_group_members", ["user_id"])

    # 4. 群消息表
    op.create_table(
        "chat_group_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("message_id", sa.String(length=64), nullable=False),
        sa.Column("group_id", sa.String(length=64), nullable=False),
        sa.Column("sender_id", sa.String(length=64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("msg_type", sa.String(length=32), server_default=sa.text("'text'"), nullable=False),
        sa.Column("media_url", sa.String(length=512), nullable=True),
        sa.Column("thumbnail_url", sa.String(length=512), nullable=True),
        sa.Column("file_name", sa.String(length=256), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("duration", sa.Integer(), nullable=True),
        sa.Column("reply_to_id", sa.String(length=64), nullable=True),
        sa.Column("forward_from_id", sa.String(length=64), nullable=True),
        sa.Column("is_recalled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("at_user_ids", sa.Text(), nullable=True),
        sa.Column("create_time", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("update_time", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["chat_groups.group_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chat_group_messages_message_id", "chat_group_messages", ["message_id"], unique=True)
    op.create_index("ix_chat_group_messages_group_id", "chat_group_messages", ["group_id"])
    op.create_index("ix_chat_group_messages_sender_id", "chat_group_messages", ["sender_id"])

    # 5. 消息收藏表
    op.create_table(
        "chat_message_favorites",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("favorite_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_message_id", sa.String(length=64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("msg_type", sa.String(length=32), nullable=False),
        sa.Column("media_url", sa.String(length=512), nullable=True),
        sa.Column("sender_id", sa.String(length=64), nullable=False),
        sa.Column("sender_name", sa.String(length=64), nullable=True),
        sa.Column("create_time", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("update_time", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chat_message_favorites_favorite_id", "chat_message_favorites", ["favorite_id"], unique=True)
    op.create_index("ix_chat_message_favorites_user_id", "chat_message_favorites", ["user_id"])
    op.create_index("ix_chat_message_favorites_source_message_id", "chat_message_favorites", ["source_message_id"])


def downgrade() -> None:
    op.drop_table("chat_message_favorites")
    op.drop_table("chat_group_messages")
    op.drop_table("chat_group_members")
    op.drop_table("chat_groups")

    op.drop_column("global_chat_messages", "is_recalled")
    op.drop_column("global_chat_messages", "forward_from_id")
    op.drop_column("global_chat_messages", "reply_to_id")
    op.drop_column("global_chat_messages", "duration")
    op.drop_column("global_chat_messages", "file_size")
    op.drop_column("global_chat_messages", "file_name")
    op.drop_column("global_chat_messages", "thumbnail_url")
    op.drop_column("global_chat_messages", "media_url")
