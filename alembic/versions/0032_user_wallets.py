"""add user wallet system

Revision ID: 0032_user_wallets
Revises: 0031_mall_order_share
Create Date: 2026-07-06 00:06:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0032_user_wallets"
down_revision = "0031_mall_order_share"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 创建 user_wallets 表
    op.create_table(
        "user_wallets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("wallet_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("balance", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("frozen_balance", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'normal'")),
        sa.Column("create_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("update_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_wallets_wallet_id", "user_wallets", ["wallet_id"], unique=True)
    op.create_index("ix_user_wallets_user_id", "user_wallets", ["user_id"], unique=True)

    # 2. 创建 wallet_records 表
    op.create_table(
        "wallet_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("record_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("direction", sa.String(length=16), nullable=False, server_default=sa.text("'earn'")),
        sa.Column("change_amount", sa.Integer(), nullable=False),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("source_id", sa.String(length=64), nullable=True),
        sa.Column("create_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("update_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_wallet_records_record_id", "wallet_records", ["record_id"], unique=True)
    op.create_index("ix_wallet_records_user_id", "wallet_records", ["user_id"], unique=False)
    op.create_index("ix_wallet_records_type", "wallet_records", ["type"], unique=False)
    op.create_index("ix_wallet_records_source_id", "wallet_records", ["source_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_wallet_records_source_id", table_name="wallet_records")
    op.drop_index("ix_wallet_records_type", table_name="wallet_records")
    op.drop_index("ix_wallet_records_user_id", table_name="wallet_records")
    op.drop_index("ix_wallet_records_record_id", table_name="wallet_records")
    op.drop_table("wallet_records")

    op.drop_index("ix_user_wallets_user_id", table_name="user_wallets")
    op.drop_index("ix_user_wallets_wallet_id", table_name="user_wallets")
    op.drop_table("user_wallets")
