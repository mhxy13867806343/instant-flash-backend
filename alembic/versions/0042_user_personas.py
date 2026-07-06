"""create user_personas, user_persona_comments, user_persona_favorites tables

Revision ID: 0042_user_personas
Revises: 0041_user_relations_fav
Create Date: 2026-07-06 11:50:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0042_user_personas"
down_revision = "0041_user_relations_fav"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 创建 user_personas 表
    op.create_table(
        "user_personas",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("persona_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=128), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("images", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False),
        sa.Column("tags", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False),
        sa.Column("privacy", sa.String(length=32), nullable=False, server_default="public"),
        sa.Column("expire_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("create_time", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("update_time", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_personas_persona_id", "user_personas", ["persona_id"], unique=True)
    op.create_index("ix_user_personas_user_id", "user_personas", ["user_id"])
    op.create_index("ix_user_personas_privacy", "user_personas", ["privacy"])
    op.create_index("ix_user_personas_expire_time", "user_personas", ["expire_time"])

    # 2. 创建 user_persona_comments 表
    op.create_table(
        "user_persona_comments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("comment_id", sa.String(length=64), nullable=False),
        sa.Column("persona_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("create_time", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("update_time", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["persona_id"], ["user_personas.persona_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_persona_comments_comment_id", "user_persona_comments", ["comment_id"], unique=True)
    op.create_index("ix_user_persona_comments_persona_id", "user_persona_comments", ["persona_id"])
    op.create_index("ix_user_persona_comments_user_id", "user_persona_comments", ["user_id"])

    # 3. 创建 user_persona_favorites 表
    op.create_table(
        "user_persona_favorites",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("favorite_id", sa.String(length=64), nullable=False),
        sa.Column("persona_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("create_time", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("update_time", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["persona_id"], ["user_personas.persona_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "persona_id", name="uq_user_persona_favorites_user_persona"),
    )
    op.create_index("ix_user_persona_favorites_favorite_id", "user_persona_favorites", ["favorite_id"], unique=True)
    op.create_index("ix_user_persona_favorites_persona_id", "user_persona_favorites", ["persona_id"])
    op.create_index("ix_user_persona_favorites_user_id", "user_persona_favorites", ["user_id"])


def downgrade() -> None:
    op.drop_table("user_persona_favorites")
    op.drop_table("user_persona_comments")
    op.drop_table("user_personas")
