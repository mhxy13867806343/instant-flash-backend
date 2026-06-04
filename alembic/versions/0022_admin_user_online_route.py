"""Add admin user online route."""

from __future__ import annotations

from alembic import op

revision = "0022_admin_user_online_route"
down_revision = "0021_user_new_phone"
branch_labels = None
depends_on = None


def _append_permission(table_name: str, role_column: str) -> None:
    op.execute(
        f"""
        UPDATE {table_name}
        SET permissions = (permissions::jsonb || '["user_online"]'::jsonb)::json,
            update_time = now(),
            last_time = now()
        WHERE {role_column} IN ('superadmin', 'admin')
          AND NOT (permissions::jsonb ? 'user_online')
        """
    )


def _remove_permission(table_name: str) -> None:
    op.execute(
        f"""
        UPDATE {table_name}
        SET permissions = (permissions::jsonb - 'user_online')::json,
            update_time = now(),
            last_time = now()
        WHERE permissions::jsonb ? 'user_online'
        """
    )


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO admin_permissions (
            permission_id, permission_key, label, description, sort, status, is_default, remark,
            create_time, update_time, last_time
        )
        SELECT 'perm_user_online', 'user_online', '在线用户', '查看用户端在线和离线用户', 180,
               'enabled', true, '系统默认权限', now(), now(), now()
        WHERE NOT EXISTS (SELECT 1 FROM admin_permissions WHERE permission_key = 'user_online')
        """
    )
    op.execute(
        """
        INSERT INTO admin_menus (
            menu_id, parent_id, title, path, name, component, redirect, icon, type, permission, sort,
            status, visible, keep_alive, affix, external_link, remark, create_time, update_time, last_time
        )
        SELECT 'menu_user_online', 'menu_system', '在线用户', 'user/online', 'UserOnline',
               'views/user/Online', NULL, 'Monitor', 'menu', 'user_online', 100,
               'enabled', true, false, false, NULL, '系统配置 - 用户端在线状态页面',
               now(), now(), now()
        WHERE NOT EXISTS (SELECT 1 FROM admin_menus WHERE menu_id = 'menu_user_online' OR name = 'UserOnline')
        """
    )
    op.execute(
        """
        UPDATE admin_menus
        SET parent_id = 'menu_system',
            title = '在线用户',
            path = 'user/online',
            name = 'UserOnline',
            component = 'views/user/Online',
            icon = 'Monitor',
            permission = 'user_online',
            sort = 100,
            status = 'enabled',
            visible = true,
            update_time = now(),
            last_time = now()
        WHERE menu_id = 'menu_user_online'
        """
    )
    _append_permission("admin_roles", "role_key")
    _append_permission("admin_accounts", "role")


def downgrade() -> None:
    op.execute("DELETE FROM admin_menus WHERE menu_id = 'menu_user_online'")
    op.execute("DELETE FROM admin_permissions WHERE permission_key = 'user_online'")
    _remove_permission("admin_roles")
    _remove_permission("admin_accounts")
