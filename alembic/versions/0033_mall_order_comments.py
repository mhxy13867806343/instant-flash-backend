"""add mall order comments

Revision ID: 0033_mall_order_comments
Revises: 0032_user_wallets
Create Date: 2026-07-06 00:12:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

# revision identifiers, used by Alembic.
revision = "0033_mall_order_comments"
down_revision = "0032_user_wallets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 向 mall_orders 增加 is_commented 状态字段
    op.add_column("mall_orders", sa.Column("is_commented", sa.Boolean(), nullable=False, server_default=sa.text("false")))

    # 2. 创建 mall_product_comments 表
    op.create_table(
        "mall_product_comments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("comment_id", sa.String(length=64), nullable=False),
        sa.Column("order_id", sa.String(length=64), nullable=False),
        sa.Column("product_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("nickname", sa.String(length=64), nullable=True),
        sa.Column("avatar", sa.String(length=512), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=False, server_default=sa.text("5")),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "images",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'approved'")),
        sa.Column("create_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("update_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mall_product_comments_comment_id", "mall_product_comments", ["comment_id"], unique=True)
    op.create_index("ix_mall_product_comments_order_id", "mall_product_comments", ["order_id"], unique=True)
    op.create_index("ix_mall_product_comments_product_id", "mall_product_comments", ["product_id"], unique=False)
    op.create_index("ix_mall_product_comments_user_id", "mall_product_comments", ["user_id"], unique=False)
    op.create_index("ix_mall_product_comments_status", "mall_product_comments", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_mall_product_comments_status", table_name="mall_product_comments")
    op.drop_index("ix_mall_product_comments_user_id", table_name="mall_product_comments")
    op.drop_index("ix_mall_product_comments_product_id", table_name="mall_product_comments")
    op.drop_index("ix_mall_product_comments_order_id", table_name="mall_product_comments")
    op.drop_index("ix_mall_product_comments_comment_id", table_name="mall_product_comments")
    op.drop_table("mall_product_comments")

    op.drop_column("mall_orders", "is_commented")
