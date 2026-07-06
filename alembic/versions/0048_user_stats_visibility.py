"""add stats visibility columns to users table

Revision ID: 0048_user_stats_visibility
Revises: 0047_aigc_works_social
Create Date: 2026-07-07 08:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0048_user_stats_visibility"
down_revision = "0047_aigc_works_social"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("show_likes", sa.Boolean(), server_default=sa.text("true"), nullable=False))
    op.add_column("users", sa.Column("show_views", sa.Boolean(), server_default=sa.text("true"), nullable=False))
    op.add_column("users", sa.Column("show_comments", sa.Boolean(), server_default=sa.text("true"), nullable=False))
    op.add_column("users", sa.Column("show_favorites", sa.Boolean(), server_default=sa.text("true"), nullable=False))


def downgrade() -> None:
    op.drop_column("users", "show_favorites")
    op.drop_column("users", "show_comments")
    op.drop_column("users", "show_views")
    op.drop_column("users", "show_likes")
