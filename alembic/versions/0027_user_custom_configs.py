"""add user custom configs table

Revision ID: 0027_user_custom_configs
Revises: 0026_user_points
Create Date: 2026-07-05 22:03:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "0027_user_custom_configs"
down_revision = "0026_user_points"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_custom_configs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("config_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("config_key", sa.String(length=128), nullable=False),
        sa.Column(
            "config_value",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=True,
        ),
        sa.Column("label", sa.String(length=128), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("create_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("update_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_time", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_custom_configs_config_id", "user_custom_configs", ["config_id"], unique=True)
    op.create_index("ix_user_custom_configs_user_id", "user_custom_configs", ["user_id"], unique=False)
    op.create_index("ix_user_custom_configs_config_key", "user_custom_configs", ["config_key"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_user_custom_configs_config_key", table_name="user_custom_configs")
    op.drop_index("ix_user_custom_configs_user_id", table_name="user_custom_configs")
    op.drop_index("ix_user_custom_configs_config_id", table_name="user_custom_configs")
    op.drop_table("user_custom_configs")
