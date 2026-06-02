from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014_admin_security_logs"
down_revision: str | None = "0013_admin_permissions_logout"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamp_columns() -> list[sa.Column]:
    return [
        sa.Column("create_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("update_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_time", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "admin_security_settings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.String(length=64), nullable=False),
        sa.Column("mfa_enabled", sa.Boolean(), nullable=False),
        sa.Column("password_policy_enabled", sa.Boolean(), nullable=False),
        sa.Column("remark", sa.Text(), nullable=True),
        *timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id"),
    )
    op.create_index(op.f("ix_admin_security_settings_account_id"), "admin_security_settings", ["account_id"], unique=False)

    op.create_table(
        "admin_operation_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("log_id", sa.String(length=64), nullable=False),
        sa.Column("account_id", sa.String(length=64), nullable=True),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("location", sa.String(length=128), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        *timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("log_id"),
    )
    op.create_index(op.f("ix_admin_operation_logs_account_id"), "admin_operation_logs", ["account_id"], unique=False)
    op.create_index(op.f("ix_admin_operation_logs_category"), "admin_operation_logs", ["category"], unique=False)
    op.create_index(op.f("ix_admin_operation_logs_log_id"), "admin_operation_logs", ["log_id"], unique=False)
    op.create_index(op.f("ix_admin_operation_logs_username"), "admin_operation_logs", ["username"], unique=False)

    op.execute(
        """
        INSERT INTO admin_permissions (
            permission_id, permission_key, label, description, sort, status, is_default, remark,
            create_time, update_time, last_time
        )
        SELECT 'perm_log', 'log', '日志管理', '后台登录日志与操作日志', 160, 'enabled', true, '系统默认权限',
               now(), now(), now()
        WHERE NOT EXISTS (SELECT 1 FROM admin_permissions WHERE permission_key = 'log')
        """
    )
    op.execute(
        """
        INSERT INTO admin_menus (
            menu_id, parent_id, title, path, name, component, redirect, icon, type, permission,
            sort, status, visible, keep_alive, affix, external_link, remark,
            create_time, update_time, last_time
        )
        SELECT 'menu_account_profile', NULL, '个人信息', 'account/profile', 'AccountProfile',
               'views/account/Profile', NULL, 'User', 'menu', NULL, 85, 'enabled',
               false, false, false, NULL, '个人中心动态路由，仅管理员和超级管理员可见',
               now(), now(), now()
        WHERE NOT EXISTS (SELECT 1 FROM admin_menus WHERE menu_id = 'menu_account_profile' OR name = 'AccountProfile')
        """
    )
    op.execute(
        """
        INSERT INTO admin_menus (
            menu_id, parent_id, title, path, name, component, redirect, icon, type, permission,
            sort, status, visible, keep_alive, affix, external_link, remark,
            create_time, update_time, last_time
        )
        SELECT 'menu_account_settings', NULL, '安全设置', 'account/settings', 'AccountSettings',
               'views/account/Settings', NULL, 'Lock', 'menu', NULL, 86, 'enabled',
               false, false, false, NULL, '个人中心动态路由，仅管理员和超级管理员可见',
               now(), now(), now()
        WHERE NOT EXISTS (SELECT 1 FROM admin_menus WHERE menu_id = 'menu_account_settings' OR name = 'AccountSettings')
        """
    )
    op.execute(
        """
        INSERT INTO admin_menus (
            menu_id, parent_id, title, path, name, component, redirect, icon, type, permission,
            sort, status, visible, keep_alive, affix, external_link, remark,
            create_time, update_time, last_time
        )
        SELECT 'menu_log', 'menu_system', '日志管理', 'log/list', 'LogList',
               'views/log/List', NULL, 'Tickets', 'menu', 'log', 80, 'enabled',
               true, false, false, NULL, NULL,
               now(), now(), now()
        WHERE NOT EXISTS (SELECT 1 FROM admin_menus WHERE menu_id = 'menu_log' OR name = 'LogList')
        """
    )
    op.execute(
        """
        UPDATE admin_menus
        SET path = 'log/list',
            component = 'views/log/List',
            parent_id = 'menu_system',
            permission = 'log',
            visible = true,
            last_time = now()
        WHERE menu_id = 'menu_log'
        """
    )
    op.execute(
        """
        UPDATE admin_accounts
        SET permissions = (permissions::jsonb || '["log"]'::jsonb)::json
        WHERE role = 'superadmin'
          AND NOT (permissions::jsonb ? 'log')
        """
    )
    op.execute(
        """
        UPDATE admin_roles
        SET permissions = (permissions::jsonb || '["log"]'::jsonb)::json
        WHERE role_key = 'superadmin'
          AND NOT (permissions::jsonb ? 'log')
        """
    )
    op.execute(
        """
        UPDATE admin_roles
        SET permissions = (permissions::jsonb || '["account"]'::jsonb)::json
        WHERE role_key = 'admin'
          AND NOT (permissions::jsonb ? 'account')
        """
    )
    op.execute(
        """
        UPDATE admin_roles
        SET permissions = (permissions::jsonb || '["log"]'::jsonb)::json
        WHERE role_key = 'admin'
          AND NOT (permissions::jsonb ? 'log')
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM admin_menus WHERE menu_id IN ('menu_account_profile', 'menu_account_settings', 'menu_log')")
    op.execute("DELETE FROM admin_permissions WHERE permission_id = 'perm_log'")
    op.drop_index(op.f("ix_admin_operation_logs_username"), table_name="admin_operation_logs")
    op.drop_index(op.f("ix_admin_operation_logs_log_id"), table_name="admin_operation_logs")
    op.drop_index(op.f("ix_admin_operation_logs_category"), table_name="admin_operation_logs")
    op.drop_index(op.f("ix_admin_operation_logs_account_id"), table_name="admin_operation_logs")
    op.drop_table("admin_operation_logs")
    op.drop_index(op.f("ix_admin_security_settings_account_id"), table_name="admin_security_settings")
    op.drop_table("admin_security_settings")
