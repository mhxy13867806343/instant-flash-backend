"""mall order enhancements: expire_at, address, user_remark; point_records expire_at

Revision ID: 0029_mall_order_enhancements
Revises: 0028_mall_system
Create Date: 2026-07-05 23:15:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0029_mall_order_enhancements"
down_revision = "0028_mall_system"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # mall_orders：新增扩展字段
    op.add_column("mall_orders", sa.Column("expire_at", sa.String(length=32), nullable=True))
    op.add_column("mall_orders", sa.Column("user_remark", sa.String(length=256), nullable=True))
    op.add_column("mall_orders", sa.Column("receiver_name", sa.String(length=64), nullable=True))
    op.add_column("mall_orders", sa.Column("receiver_phone", sa.String(length=32), nullable=True))
    op.add_column("mall_orders", sa.Column("receiver_address", sa.String(length=512), nullable=True))

    # point_records：新增积分有效期字段
    op.add_column(
        "point_records",
        sa.Column("expire_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("point_records", "expire_at")
    op.drop_column("mall_orders", "receiver_address")
    op.drop_column("mall_orders", "receiver_phone")
    op.drop_column("mall_orders", "receiver_name")
    op.drop_column("mall_orders", "user_remark")
    op.drop_column("mall_orders", "expire_at")
