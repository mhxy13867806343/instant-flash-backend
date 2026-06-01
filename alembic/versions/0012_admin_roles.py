from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_admin_roles"
down_revision: str | None = "0011_menu_management"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_PERMISSIONS = '["dashboard", "user", "content", "comment", "simulator", "account", "announcement", "version", "tag", "region", "dict", "menu", "message", "agreement"]'


def timestamp_columns() -> list[sa.Column]:
    return [
        sa.Column("create_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("update_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_time", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.alter_column("admin_accounts", "role", existing_type=sa.String(length=32), type_=sa.String(length=64), existing_nullable=False)
    op.create_table(
        "admin_roles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("role_id", sa.String(length=64), nullable=False),
        sa.Column("role_key", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=64), nullable=False),
        sa.Column("icon", sa.String(length=64), nullable=True),
        sa.Column("permissions", sa.JSON(), nullable=False),
        sa.Column("sort", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("remark", sa.Text(), nullable=True),
        *timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("role_id"),
        sa.UniqueConstraint("role_key"),
    )
    op.create_index(op.f("ix_admin_roles_role_id"), "admin_roles", ["role_id"], unique=False)
    op.execute(
        f"""
        INSERT INTO admin_roles (
            role_id, role_key, label, icon, permissions, sort, status, is_default, remark,
            create_time, update_time, last_time
        )
        VALUES
            ('role_superadmin', 'superadmin', '超级管理员', 'StarFilled', '{DEFAULT_PERMISSIONS}', 10, 'enabled', true, '系统内置超级管理员角色', now(), now(), now()),
            ('role_admin', 'admin', '管理员', 'UserFilled', '["dashboard", "user", "content", "comment", "tag", "region", "message"]', 20, 'enabled', true, '系统内置管理员角色', now(), now(), now()),
            ('role_operator', 'operator', '运营员', 'Setting', '["dashboard", "content", "comment", "tag"]', 30, 'enabled', true, '系统内置运营角色', now(), now(), now()),
            ('role_viewer', 'viewer', '观察员', 'View', '["dashboard"]', 40, 'enabled', true, '系统内置观察员角色', now(), now(), now())
        """
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_admin_roles_role_id"), table_name="admin_roles")
    op.drop_table("admin_roles")
    op.alter_column("admin_accounts", "role", existing_type=sa.String(length=64), type_=sa.String(length=32), existing_nullable=False)
