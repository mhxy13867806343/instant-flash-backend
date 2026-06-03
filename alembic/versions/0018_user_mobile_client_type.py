"""add user mobile client type

Revision ID: 0018_user_mobile_client_type
Revises: 0017_rate_limit_access_rules
Create Date: 2026-06-03 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0018_user_mobile_client_type"
down_revision = "0017_rate_limit_access_rules"
branch_labels = None
depends_on = None


USER_FK_TABLES = ("posts", "comments", "post_likes", "post_shares")


def _recreate_user_fks_with_cascade() -> None:
    for table_name in USER_FK_TABLES:
        constraint_name = f"{table_name}_user_id_fkey"
        op.drop_constraint(constraint_name, table_name, type_="foreignkey")
        op.create_foreign_key(
            constraint_name,
            table_name,
            "users",
            ["user_id"],
            ["user_id"],
            onupdate="CASCADE",
        )


def _recreate_user_fks_without_cascade() -> None:
    for table_name in USER_FK_TABLES:
        constraint_name = f"{table_name}_user_id_fkey"
        op.drop_constraint(constraint_name, table_name, type_="foreignkey")
        op.create_foreign_key(
            constraint_name,
            table_name,
            "users",
            ["user_id"],
            ["user_id"],
        )


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    op.add_column("users", sa.Column("client_type", sa.String(length=32), nullable=True))
    op.add_column("users", sa.Column("client_subtype", sa.String(length=64), nullable=True))
    op.create_index(op.f("ix_users_client_type"), "users", ["client_type"], unique=False)

    if dialect == "postgresql":
        _recreate_user_fks_with_cascade()

    op.execute(
        """
        UPDATE users
        SET phone = substr(user_id, 4)
        WHERE user_id LIKE 'h5-%'
          AND (phone IS NULL OR phone = '')
          AND NOT EXISTS (
              SELECT 1 FROM users AS duplicated
              WHERE duplicated.phone = substr(users.user_id, 4)
          )
        """
    )
    op.execute(
        """
        UPDATE users
        SET client_type = COALESCE(client_type, 'h5')
        WHERE user_id LIKE 'h5-%'
        """
    )
    op.execute(
        """
        UPDATE users
        SET user_id = 'mp-' || substr(user_id, 4)
        WHERE user_id LIKE 'h5-%'
          AND NOT EXISTS (
              SELECT 1 FROM users AS duplicated
              WHERE duplicated.user_id = 'mp-' || substr(users.user_id, 4)
          )
        """
    )
    op.execute(
        """
        UPDATE comments
        SET reply_to_user_id = 'mp-' || substr(reply_to_user_id, 4)
        WHERE reply_to_user_id LIKE 'h5-%'
        """
    )
    op.execute(
        """
        UPDATE messages
        SET user_id = 'mp-' || substr(user_id, 4)
        WHERE user_id LIKE 'h5-%'
        """
    )
    op.execute(
        """
        UPDATE messages
        SET sender_id = 'mp-' || substr(sender_id, 4)
        WHERE sender_id LIKE 'h5-%'
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        _recreate_user_fks_without_cascade()

    op.drop_index(op.f("ix_users_client_type"), table_name="users")
    op.drop_column("users", "client_subtype")
    op.drop_column("users", "client_type")
