"""add post location fields

Revision ID: 0019_post_location_feed_search
Revises: 0018_user_mobile_client_type
Create Date: 2026-06-03 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0019_post_location_feed_search"
down_revision = "0018_user_mobile_client_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("posts", sa.Column("location", sa.String(length=128), nullable=True))
    op.add_column("posts", sa.Column("province", sa.String(length=64), nullable=True))
    op.add_column("posts", sa.Column("city", sa.String(length=64), nullable=True))
    op.add_column("posts", sa.Column("district", sa.String(length=64), nullable=True))
    op.create_index(op.f("ix_posts_location"), "posts", ["location"], unique=False)
    op.create_index(op.f("ix_posts_city"), "posts", ["city"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_posts_city"), table_name="posts")
    op.drop_index(op.f("ix_posts_location"), table_name="posts")
    op.drop_column("posts", "district")
    op.drop_column("posts", "city")
    op.drop_column("posts", "province")
    op.drop_column("posts", "location")
