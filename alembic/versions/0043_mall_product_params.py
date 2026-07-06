"""add new parameters to mall_products table

Revision ID: 0043_mall_product_params
Revises: 0042_user_personas
Create Date: 2026-07-06 12:35:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0043_mall_product_params"
down_revision = "0042_user_personas"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("mall_products", sa.Column("is_hot", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("mall_products", sa.Column("is_top10", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("mall_products", sa.Column("is_today", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("mall_products", sa.Column("allow_multiple_purchase", sa.Boolean(), server_default="true", nullable=False))
    op.add_column("mall_products", sa.Column("is_time_slot", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("mall_products", sa.Column("time_slot", sa.String(length=64), nullable=True))

    op.create_index("ix_mall_products_is_hot", "mall_products", ["is_hot"])
    op.create_index("ix_mall_products_is_top10", "mall_products", ["is_top10"])
    op.create_index("ix_mall_products_is_today", "mall_products", ["is_today"])
    op.create_index("ix_mall_products_is_time_slot", "mall_products", ["is_time_slot"])


def downgrade() -> None:
    op.drop_index("ix_mall_products_is_time_slot", table_name="mall_products")
    op.drop_index("ix_mall_products_is_today", table_name="mall_products")
    op.drop_index("ix_mall_products_is_top10", table_name="mall_products")
    op.drop_index("ix_mall_products_is_hot", table_name="mall_products")

    op.drop_column("mall_products", "time_slot")
    op.drop_column("mall_products", "is_time_slot")
    op.drop_column("mall_products", "allow_multiple_purchase")
    op.drop_column("mall_products", "is_today")
    op.drop_column("mall_products", "is_top10")
    op.drop_column("mall_products", "is_hot")
