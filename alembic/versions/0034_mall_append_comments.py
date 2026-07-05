"""add mall order comment appends

Revision ID: 0034_mall_append_comments
Revises: 0033_mall_order_comments
Create Date: 2026-07-06 00:17:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

# revision identifiers, used by Alembic.
revision = "0034_mall_append_comments"
down_revision = "0033_mall_order_comments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 创建 mall_product_comment_appends 表
    op.create_table(
        "mall_product_comment_appends",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("append_id", sa.String(length=64), nullable=False),
        sa.Column("comment_id", sa.String(length=64), nullable=False),
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
        sa.ForeignKeyConstraint(["comment_id"], ["mall_product_comments.comment_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mall_product_comment_appends_append_id", "mall_product_comment_appends", ["append_id"], unique=True)
    op.create_index("ix_mall_product_comment_appends_comment_id", "mall_product_comment_appends", ["comment_id"], unique=False)
    op.create_index("ix_mall_product_comment_appends_status", "mall_product_comment_appends", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_mall_product_comment_appends_status", table_name="mall_product_comment_appends")
    op.drop_index("ix_mall_product_comment_appends_comment_id", table_name="mall_product_comment_appends")
    op.drop_index("ix_mall_product_comment_appends_append_id", table_name="mall_product_comment_appends")
    op.drop_table("mall_product_comment_appends")
