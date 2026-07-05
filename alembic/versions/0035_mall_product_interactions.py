"""add mall product interactions: likes, favorites, shares

Revision ID: 0035_mall_product_interactions
Revises: 0034_mall_append_comments
Create Date: 2026-07-06 00:20:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0035_mall_product_interactions"
down_revision = "0034_mall_append_comments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 创建 mall_product_likes 表
    op.create_table(
        "mall_product_likes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("product_id", sa.String(length=64), nullable=False),
        sa.Column("create_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("update_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["product_id"], ["mall_products.product_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "product_id", name="uq_mall_product_likes_user_product"),
    )
    op.create_index("ix_mall_product_likes_product_id", "mall_product_likes", ["product_id"], unique=False)
    op.create_index("ix_mall_product_likes_user_id", "mall_product_likes", ["user_id"], unique=False)

    # 2. 创建 mall_product_favorites 表
    op.create_table(
        "mall_product_favorites",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("product_id", sa.String(length=64), nullable=False),
        sa.Column("create_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("update_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["product_id"], ["mall_products.product_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "product_id", name="uq_mall_product_favorites_user_product"),
    )
    op.create_index("ix_mall_product_favorites_product_id", "mall_product_favorites", ["product_id"], unique=False)
    op.create_index("ix_mall_product_favorites_user_id", "mall_product_favorites", ["user_id"], unique=False)

    # 3. 创建 mall_product_shares 表
    op.create_table(
        "mall_product_shares",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=True),
        sa.Column("product_id", sa.String(length=64), nullable=False),
        sa.Column("platform", sa.String(length=64), nullable=True),
        sa.Column("create_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("update_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["product_id"], ["mall_products.product_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mall_product_shares_product_id", "mall_product_shares", ["product_id"], unique=False)
    op.create_index("ix_mall_product_shares_user_id", "mall_product_shares", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_table("mall_product_shares")
    op.drop_table("mall_product_favorites")
    op.drop_table("mall_product_likes")
