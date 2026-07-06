"""add pay_method to wallet_records

Revision ID: 0038_wallet_pay_method
Revises: 0037_global_chat_system
Create Date: 2026-07-06 09:18:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0038_wallet_pay_method"
down_revision = "0037_global_chat_system"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("wallet_records", sa.Column("pay_method", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("wallet_records", "pay_method")
