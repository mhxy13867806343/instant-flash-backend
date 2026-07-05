"""add share_token to mall_orders

Revision ID: 0031_mall_order_share
Revises: 0030_mall_express
Create Date: 2026-07-05 23:45:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0031_mall_order_share"
down_revision = "0030_mall_express"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("mall_orders", sa.Column("share_token", sa.String(length=64), nullable=True))
    op.create_index("ix_mall_orders_share_token", "mall_orders", ["share_token"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_mall_orders_share_token", table_name="mall_orders")
    op.drop_column("mall_orders", "share_token")
