"""add global chat system

Revision ID: 0037_global_chat_system
Revises: 0036_mall_interactions_tables
Create Date: 2026-07-06 00:30:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0037_global_chat_system"
down_revision = "0036_mall_interactions_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 创建 global_chat_sessions 表
    op.create_table(
        "global_chat_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("user_one_id", sa.String(length=64), nullable=False),
        sa.Column("user_two_id", sa.String(length=64), nullable=False),
        sa.Column("last_message", sa.Text(), nullable=True),
        sa.Column("last_message_time", sa.String(length=32), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("create_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("update_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_global_chat_sessions_session_id", "global_chat_sessions", ["session_id"], unique=True)
    op.create_index("ix_global_chat_sessions_user_one_id", "global_chat_sessions", ["user_one_id"], unique=False)
    op.create_index("ix_global_chat_sessions_user_two_id", "global_chat_sessions", ["user_two_id"], unique=False)

    # 2. 创建 global_chat_messages 表
    op.create_table(
        "global_chat_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("message_id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("sender_id", sa.String(length=64), nullable=False),
        sa.Column("receiver_id", sa.String(length=64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("msg_type", sa.String(length=32), nullable=False, server_default=sa.text("'text'")),
        sa.Column("product_id", sa.String(length=64), nullable=True),
        sa.Column("bargain_id", sa.String(length=64), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("create_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("update_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["session_id"], ["global_chat_sessions.session_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_global_chat_messages_message_id", "global_chat_messages", ["message_id"], unique=True)
    op.create_index("ix_global_chat_messages_session_id", "global_chat_messages", ["session_id"], unique=False)
    op.create_index("ix_global_chat_messages_sender_id", "global_chat_messages", ["sender_id"], unique=False)
    op.create_index("ix_global_chat_messages_receiver_id", "global_chat_messages", ["receiver_id"], unique=False)
    op.create_index("ix_global_chat_messages_product_id", "global_chat_messages", ["product_id"], unique=False)
    op.create_index("ix_global_chat_messages_bargain_id", "global_chat_messages", ["bargain_id"], unique=False)


def downgrade() -> None:
    op.drop_table("global_chat_messages")
    op.drop_table("global_chat_sessions")
