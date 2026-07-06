"""add aigc works social tables and columns

Revision ID: 0047_aigc_works_social
Revises: 0046_ai_model_system
Create Date: 2026-07-06 23:59:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0047_aigc_works_social"
down_revision = "0046_ai_model_system"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 为 ai_model_usage_records 新增字段
    op.add_column("ai_model_usage_records", sa.Column("title", sa.String(length=128), nullable=True))
    op.add_column("ai_model_usage_records", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("ai_model_usage_records", sa.Column("visibility", sa.String(length=32), nullable=False, server_default="private"))
    op.add_column("ai_model_usage_records", sa.Column("like_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("ai_model_usage_records", sa.Column("comment_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("ai_model_usage_records", sa.Column("favorite_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("ai_model_usage_records", sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"))

    # 2. 创建 ai_model_usage_record_likes 表
    op.create_table(
        "ai_model_usage_record_likes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("record_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("create_time", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("update_time", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_time", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["record_id"], ["ai_model_usage_records.record_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("record_id", "user_id", name="uq_aim_record_like"),
    )
    op.create_index("ix_ai_model_usage_record_likes_record_id", "ai_model_usage_record_likes", ["record_id"])
    op.create_index("ix_ai_model_usage_record_likes_user_id", "ai_model_usage_record_likes", ["user_id"])

    # 3. 创建 ai_model_usage_record_favorites 表
    op.create_table(
        "ai_model_usage_record_favorites",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("record_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("create_time", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("update_time", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_time", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["record_id"], ["ai_model_usage_records.record_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("record_id", "user_id", name="uq_aim_record_fav"),
    )
    op.create_index("ix_ai_model_usage_record_favorites_record_id", "ai_model_usage_record_favorites", ["record_id"])
    op.create_index("ix_ai_model_usage_record_favorites_user_id", "ai_model_usage_record_favorites", ["user_id"])

    # 4. 创建 ai_model_usage_record_comments 表
    op.create_table(
        "ai_model_usage_record_comments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("comment_id", sa.String(length=64), nullable=False),
        sa.Column("record_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("parent_id", sa.String(length=64), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("create_time", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("update_time", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_time", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["record_id"], ["ai_model_usage_records.record_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
    )
    op.create_index("ix_ai_model_usage_record_comments_comment_id", "ai_model_usage_record_comments", ["comment_id"], unique=True)
    op.create_index("ix_ai_model_usage_record_comments_record_id", "ai_model_usage_record_comments", ["record_id"])
    op.create_index("ix_ai_model_usage_record_comments_user_id", "ai_model_usage_record_comments", ["user_id"])
    op.create_index("ix_ai_model_usage_record_comments_parent_id", "ai_model_usage_record_comments", ["parent_id"])


def downgrade() -> None:
    op.drop_table("ai_model_usage_record_comments")
    op.drop_table("ai_model_usage_record_favorites")
    op.drop_table("ai_model_usage_record_likes")

    op.drop_column("ai_model_usage_records", "view_count")
    op.drop_column("ai_model_usage_records", "favorite_count")
    op.drop_column("ai_model_usage_records", "comment_count")
    op.drop_column("ai_model_usage_records", "like_count")
    op.drop_column("ai_model_usage_records", "visibility")
    op.drop_column("ai_model_usage_records", "description")
    op.drop_column("ai_model_usage_records", "title")
