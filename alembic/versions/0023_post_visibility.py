"""add post visibility

Revision ID: 0023_post_visibility
Revises: 0022_admin_user_online_route
Create Date: 2026-06-04 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0023_post_visibility"
down_revision = "0022_admin_user_online_route"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "posts",
        sa.Column("visibility", sa.String(length=32), nullable=False, server_default="public"),
    )


def downgrade() -> None:
    op.drop_column("posts", "visibility")
