"""add user third party bindings table

Revision ID: 0040_user_third_party_bindings
Revises: 0039_chat_system_enhance
Create Date: 2026-07-06 10:20:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0040_user_third_party_bindings"
down_revision = "0039_chat_system_enhance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_third_party_bindings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("binding_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("openid", sa.String(length=128), nullable=False),
        sa.Column("unionid", sa.String(length=128), nullable=True),
        sa.Column("nickname", sa.String(length=64), nullable=True),
        sa.Column("avatar", sa.Text(), nullable=True),
        sa.Column("extra_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("create_time", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("update_time", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("platform", "openid", name="uq_user_third_party_platform_openid"),
        sa.UniqueConstraint("user_id", "platform", name="uq_user_third_party_user_platform"),
    )
    op.create_index("ix_user_third_party_bindings_binding_id", "user_third_party_bindings", ["binding_id"], unique=True)
    op.create_index("ix_user_third_party_bindings_user_id", "user_third_party_bindings", ["user_id"])
    op.create_index("ix_user_third_party_bindings_platform", "user_third_party_bindings", ["platform"])
    op.create_index("ix_user_third_party_bindings_openid", "user_third_party_bindings", ["openid"])
    op.create_index("ix_user_third_party_bindings_unionid", "user_third_party_bindings", ["unionid"])


def downgrade() -> None:
    op.drop_table("user_third_party_bindings")
