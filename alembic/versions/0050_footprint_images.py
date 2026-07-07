"""add images column to user footprints table

Revision ID: 0050_footprint_images
Revises: 0049_user_footprints
Create Date: 2026-07-07 09:30:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0050_footprint_images"
down_revision = "0049_user_footprints"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Postgres uses postgresql.JSONB, SQLite and others fall back to JSON
    op.add_column(
        "user_footprints",
        sa.Column(
            "images",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            server_default=sa.text("'[]'"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("user_footprints", "images")
