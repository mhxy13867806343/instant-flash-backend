"""create user footprints table

Revision ID: 0049_user_footprints
Revises: 0048_user_stats_visibility
Create Date: 2026-07-07 09:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0049_user_footprints"
down_revision = "0048_user_stats_visibility"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_footprints",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("footprint_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("location_name", sa.String(length=256), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("create_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("update_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_user_footprints_footprint_id", "user_footprints", ["footprint_id"], unique=True)
    op.create_index("ix_user_footprints_user_id", "user_footprints", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_user_footprints_user_id", table_name="user_footprints")
    op.drop_index("ix_user_footprints_footprint_id", table_name="user_footprints")
    op.drop_table("user_footprints")
