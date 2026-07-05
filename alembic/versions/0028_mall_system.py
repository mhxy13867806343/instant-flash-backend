"""add mall system: products, orders, payment_methods, settings

Revision ID: 0028_mall_system
Revises: 0027_user_custom_configs
Create Date: 2026-07-05 22:49:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "0028_mall_system"
down_revision = "0027_user_custom_configs"
branch_labels = None
depends_on = None

# 默认预置的支付方式
DEFAULT_PAYMENT_METHODS = [
    {
        "method_id": "pay_wechat",
        "name": "微信支付",
        "logo": "",
        "type": "wechat",
        "type_value": None,
        "status": "enabled",
        "sort": 10,
        "remark": "系统默认预置",
    },
    {
        "method_id": "pay_alipay",
        "name": "支付宝",
        "logo": "",
        "type": "alipay",
        "type_value": None,
        "status": "enabled",
        "sort": 20,
        "remark": "系统默认预置",
    },
]


def upgrade() -> None:
    # 1. 商城全局设置表
    op.create_table(
        "mall_settings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("points_switch", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("create_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("update_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    # 插入默认设置行
    op.execute(
        sa.text(
            "INSERT INTO mall_settings (id, points_switch, create_time, update_time, last_time) "
            "VALUES (1, false, NOW(), NOW(), NOW()) "
            "ON CONFLICT (id) DO NOTHING"
        )
    )

    # 2. 商品表
    op.create_table(
        "mall_products",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("product_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "images",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column("cover_image", sa.String(length=512), nullable=True),
        sa.Column("cover_video", sa.String(length=512), nullable=True),
        sa.Column("original_price", sa.Integer(), nullable=False),
        sa.Column("current_price", sa.Integer(), nullable=False),
        sa.Column("points_cost", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("points_only", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("stock", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("sold_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'off_shelf'")),
        sa.Column("sort", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("create_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("update_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mall_products_product_id", "mall_products", ["product_id"], unique=True)
    op.create_index("ix_mall_products_status", "mall_products", ["status"], unique=False)

    # 3. 订单表
    op.create_table(
        "mall_orders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("order_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("product_id", sa.String(length=64), nullable=False),
        sa.Column("product_title", sa.String(length=128), nullable=False),
        sa.Column("product_image", sa.String(length=512), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("unit_price", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_price", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("points_used", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("pay_type", sa.String(length=32), nullable=True),
        sa.Column("pay_type_value", sa.String(length=256), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'pending_pay'")),
        sa.Column("paid_at", sa.String(length=32), nullable=True),
        sa.Column("shipped_at", sa.String(length=32), nullable=True),
        sa.Column("completed_at", sa.String(length=32), nullable=True),
        sa.Column("cancelled_at", sa.String(length=32), nullable=True),
        sa.Column("cancel_reason", sa.String(length=256), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("create_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("update_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mall_orders_order_id", "mall_orders", ["order_id"], unique=True)
    op.create_index("ix_mall_orders_user_id", "mall_orders", ["user_id"], unique=False)
    op.create_index("ix_mall_orders_product_id", "mall_orders", ["product_id"], unique=False)
    op.create_index("ix_mall_orders_status", "mall_orders", ["status"], unique=False)

    # 4. 支付方式表
    op.create_table(
        "mall_payment_methods",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("method_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("logo", sa.String(length=512), nullable=True),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("type_value", sa.String(length=256), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'enabled'")),
        sa.Column("sort", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("create_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("update_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mall_payment_methods_method_id", "mall_payment_methods", ["method_id"], unique=True)
    op.create_index("ix_mall_payment_methods_type", "mall_payment_methods", ["type"], unique=True)

    # 预置默认支付方式（微信 + 支付宝）
    now_sql = sa.func.now()
    for m in DEFAULT_PAYMENT_METHODS:
        op.execute(
            sa.text(
                "INSERT INTO mall_payment_methods "
                "(method_id, name, logo, type, type_value, status, sort, remark, create_time, update_time, last_time) "
                "VALUES (:method_id, :name, :logo, :type, :type_value, :status, :sort, :remark, NOW(), NOW(), NOW()) "
                "ON CONFLICT (type) DO NOTHING"
            ).bindparams(**m)
        )


def downgrade() -> None:
    op.drop_index("ix_mall_payment_methods_type", table_name="mall_payment_methods")
    op.drop_index("ix_mall_payment_methods_method_id", table_name="mall_payment_methods")
    op.drop_table("mall_payment_methods")

    op.drop_index("ix_mall_orders_status", table_name="mall_orders")
    op.drop_index("ix_mall_orders_product_id", table_name="mall_orders")
    op.drop_index("ix_mall_orders_user_id", table_name="mall_orders")
    op.drop_index("ix_mall_orders_order_id", table_name="mall_orders")
    op.drop_table("mall_orders")

    op.drop_index("ix_mall_products_status", table_name="mall_products")
    op.drop_index("ix_mall_products_product_id", table_name="mall_products")
    op.drop_table("mall_products")

    op.drop_table("mall_settings")
