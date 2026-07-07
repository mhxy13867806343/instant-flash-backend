"""add clone fields to mall products table

Revision ID: 0051_product_clone_fields
Revises: 0050_footprint_images
Create Date: 2026-07-07 11:20:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0051_product_clone_fields"
down_revision = "0050_footprint_images"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "mall_products",
        sa.Column(
            "is_cloned",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "mall_products",
        sa.Column("clone_url", sa.String(length=512), nullable=True),
    )
    op.create_index("ix_mall_products_is_cloned", "mall_products", ["is_cloned"])


def downgrade() -> None:
    op.drop_index("ix_mall_products_is_cloned", table_name="mall_products")
    op.drop_column("mall_products", "clone_url")
    op.drop_column("mall_products", "is_cloned")
