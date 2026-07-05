"""add mall interactions: logistics, customer service, chat, bargaining

Revision ID: 0036_mall_interactions_tables
Revises: 0035_mall_product_interactions
Create Date: 2026-07-06 00:26:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

# revision identifiers, used by Alembic.
revision = "0036_mall_interactions_tables"
down_revision = "0035_mall_product_interactions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 创建 mall_order_logistics_steps 表
    op.create_table(
        "mall_order_logistics_steps",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("logistics_id", sa.String(length=64), nullable=False),
        sa.Column("order_id", sa.String(length=64), nullable=False),
        sa.Column("step_time", sa.String(length=32), nullable=False),
        sa.Column("content", sa.String(length=256), nullable=False),
        sa.Column("create_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("update_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["order_id"], ["mall_orders.order_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mall_order_logistics_steps_logistics_id", "mall_order_logistics_steps", ["logistics_id"], unique=True)
    op.create_index("ix_mall_order_logistics_steps_order_id", "mall_order_logistics_steps", ["order_id"], unique=False)

    # 2. 创建 mall_customer_services 表
    op.create_table(
        "mall_customer_services",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("cs_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("avatar", sa.String(length=512), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'active'")),
        sa.Column("sort", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("create_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("update_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mall_customer_services_cs_id", "mall_customer_services", ["cs_id"], unique=True)
    op.create_index("ix_mall_customer_services_status", "mall_customer_services", ["status"], unique=False)

    # 3. 创建 mall_chat_sessions 表
    op.create_table(
        "mall_chat_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("cs_id", sa.String(length=64), nullable=False),
        sa.Column("product_id", sa.String(length=64), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("create_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("update_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["cs_id"], ["mall_customer_services.cs_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mall_chat_sessions_session_id", "mall_chat_sessions", ["session_id"], unique=True)
    op.create_index("ix_mall_chat_sessions_user_id", "mall_chat_sessions", ["user_id"], unique=False)
    op.create_index("ix_mall_chat_sessions_cs_id", "mall_chat_sessions", ["cs_id"], unique=False)

    # 4. 创建 mall_chat_messages 表
    op.create_table(
        "mall_chat_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("message_id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("sender_type", sa.String(length=32), nullable=False),
        sa.Column("sender_id", sa.String(length=64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("msg_type", sa.String(length=32), nullable=False, server_default=sa.text("'text'")),
        sa.Column("bargain_id", sa.String(length=64), nullable=True),
        sa.Column("create_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("update_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["session_id"], ["mall_chat_sessions.session_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mall_chat_messages_message_id", "mall_chat_messages", ["message_id"], unique=True)
    op.create_index("ix_mall_chat_messages_session_id", "mall_chat_messages", ["session_id"], unique=False)
    op.create_index("ix_mall_chat_messages_bargain_id", "mall_chat_messages", ["bargain_id"], unique=False)

    # 5. 创建 mall_product_bargains 表
    op.create_table(
        "mall_product_bargains",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("bargain_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("product_id", sa.String(length=64), nullable=False),
        sa.Column("original_price", sa.Integer(), nullable=False),
        sa.Column("bargain_price", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("create_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("update_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["product_id"], ["mall_products.product_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mall_product_bargains_bargain_id", "mall_product_bargains", ["bargain_id"], unique=True)
    op.create_index("ix_mall_product_bargains_user_id", "mall_product_bargains", ["user_id"], unique=False)
    op.create_index("ix_mall_product_bargains_product_id", "mall_product_bargains", ["product_id"], unique=False)
    op.create_index("ix_mall_product_bargains_status", "mall_product_bargains", ["status"], unique=False)


def downgrade() -> None:
    op.drop_table("mall_product_bargains")
    op.drop_table("mall_chat_messages")
    op.drop_table("mall_chat_sessions")
    op.drop_table("mall_customer_services")
    op.drop_table("mall_order_logistics_steps")
