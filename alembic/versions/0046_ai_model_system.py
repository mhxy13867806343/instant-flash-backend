"""add ai model system tables and user model points columns

Revision ID: 0046_ai_model_system
Revises: 0045_user_deactivation
Create Date: 2026-07-06 23:42:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "0046_ai_model_system"
down_revision = "0045_user_deactivation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- users 表新增字段 ----
    op.add_column("users", sa.Column("model_points", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("daily_model_points", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("model_vip_level", sa.String(length=32), nullable=True))
    op.add_column("users", sa.Column("model_vip_expire_time", sa.DateTime(timezone=True), nullable=True))

    # ---- ai_models 表 ----
    op.create_table(
        "ai_models",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("model_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("icon", sa.String(length=512), nullable=True),
        sa.Column("cover", sa.String(length=512), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("points_per_use", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("channel", sa.String(length=32), nullable=False, server_default="standard"),
        sa.Column("features", JSONB(), nullable=False, server_default="[]"),
        sa.Column("sort", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="enabled"),
        sa.Column("create_time", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("update_time", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_time", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_models_model_id", "ai_models", ["model_id"], unique=True)
    op.create_index("ix_ai_models_type", "ai_models", ["type"])

    # ---- ai_model_plans 表 ----
    op.create_table(
        "ai_model_plans",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("plan_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("tier", sa.String(length=32), nullable=False),
        sa.Column("period_type", sa.String(length=16), nullable=False),
        sa.Column("duration_days", sa.Integer(), nullable=False),
        sa.Column("original_price", sa.Integer(), nullable=False),
        sa.Column("current_price", sa.Integer(), nullable=False),
        sa.Column("points_monthly", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("points_conversion_rate", sa.String(length=64), nullable=True),
        sa.Column("features", JSONB(), nullable=False, server_default="[]"),
        sa.Column("badge", sa.String(length=64), nullable=True),
        sa.Column("is_recommended", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("sort", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="enabled"),
        sa.Column("create_time", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("update_time", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_time", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_model_plans_plan_id", "ai_model_plans", ["plan_id"], unique=True)
    op.create_index("ix_ai_model_plans_tier", "ai_model_plans", ["tier"])
    op.create_index("ix_ai_model_plans_period_type", "ai_model_plans", ["period_type"])

    # ---- ai_model_promotions 表 ----
    op.create_table(
        "ai_model_promotions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("promotion_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("discount_rate", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("extra_points_pct", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("applicable_plans", JSONB(), nullable=False, server_default="[]"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="enabled"),
        sa.Column("create_time", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("update_time", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_time", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_model_promotions_promotion_id", "ai_model_promotions", ["promotion_id"], unique=True)

    # ---- ai_model_usage_records 表 ----
    op.create_table(
        "ai_model_usage_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("record_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("model_id", sa.String(length=64), nullable=False),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("model_type", sa.String(length=32), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=True),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("result_type", sa.String(length=32), nullable=False, server_default="text"),
        sa.Column("points_consumed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="completed"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("create_time", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("update_time", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_time", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], onupdate="CASCADE"),
    )
    op.create_index("ix_ai_model_usage_records_record_id", "ai_model_usage_records", ["record_id"], unique=True)
    op.create_index("ix_ai_model_usage_records_user_id", "ai_model_usage_records", ["user_id"])
    op.create_index("ix_ai_model_usage_records_model_id", "ai_model_usage_records", ["model_id"])

    # ---- ai_model_point_grants 表 ----
    op.create_table(
        "ai_model_point_grants",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("grant_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("grant_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("remaining", sa.Integer(), nullable=False),
        sa.Column("expire_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("create_time", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("update_time", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_time", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], onupdate="CASCADE"),
    )
    op.create_index("ix_ai_model_point_grants_grant_id", "ai_model_point_grants", ["grant_id"], unique=True)
    op.create_index("ix_ai_model_point_grants_user_id", "ai_model_point_grants", ["user_id"])
    op.create_index("ix_ai_model_point_grants_grant_date", "ai_model_point_grants", ["grant_date"])

    # ---- ai_model_subscriptions 表 ----
    op.create_table(
        "ai_model_subscriptions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("subscription_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("plan_id", sa.String(length=64), nullable=False),
        sa.Column("plan_name", sa.String(length=128), nullable=False),
        sa.Column("period_type", sa.String(length=16), nullable=False),
        sa.Column("pay_amount", sa.Integer(), nullable=False),
        sa.Column("original_amount", sa.Integer(), nullable=False),
        sa.Column("discount_amount", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("promotion_id", sa.String(length=64), nullable=True),
        sa.Column("pay_method", sa.String(length=32), nullable=True),
        sa.Column("pay_status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("points_granted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("auto_renew", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("create_time", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("update_time", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_time", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], onupdate="CASCADE"),
    )
    op.create_index("ix_ai_model_subscriptions_subscription_id", "ai_model_subscriptions", ["subscription_id"], unique=True)
    op.create_index("ix_ai_model_subscriptions_user_id", "ai_model_subscriptions", ["user_id"])
    op.create_index("ix_ai_model_subscriptions_plan_id", "ai_model_subscriptions", ["plan_id"])
    op.create_index("ix_ai_model_subscriptions_promotion_id", "ai_model_subscriptions", ["promotion_id"])


def downgrade() -> None:
    op.drop_table("ai_model_subscriptions")
    op.drop_table("ai_model_point_grants")
    op.drop_table("ai_model_usage_records")
    op.drop_table("ai_model_promotions")
    op.drop_table("ai_model_plans")
    op.drop_table("ai_models")

    op.drop_column("users", "model_vip_expire_time")
    op.drop_column("users", "model_vip_level")
    op.drop_column("users", "daily_model_points")
    op.drop_column("users", "model_points")
