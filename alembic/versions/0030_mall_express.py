"""add express columns to mall_orders

Revision ID: 0030_mall_express
Revises: 0029_mall_order_enhancements
Create Date: 2026-07-05 23:35:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0030_mall_express"
down_revision = "0029_mall_order_enhancements"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("mall_orders", sa.Column("express_company", sa.String(length=64), nullable=True))
    op.add_column("mall_orders", sa.Column("express_no", sa.String(length=128), nullable=True))


def downgrade() -> None:
    op.drop_column("mall_orders", "express_no")
    op.drop_column("mall_orders", "express_company")
