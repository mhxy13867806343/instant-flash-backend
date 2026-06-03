"""add admin like share routes

Revision ID: 0020_admin_like_share_routes
Revises: 0019_post_location_feed_search
Create Date: 2026-06-03 00:00:00.000000
"""

from __future__ import annotations

from alembic import op


revision = "0020_admin_like_share_routes"
down_revision = "0019_post_location_feed_search"
branch_labels = None
depends_on = None


def _append_json_permissions(table_name: str, role_column: str) -> None:
    op.execute(
        f"""
        UPDATE {table_name}
        SET permissions = (permissions::jsonb || '["like", "share"]'::jsonb)::json
        WHERE {role_column} IN ('superadmin', 'admin', 'operator')
          AND NOT (permissions::jsonb ? 'like')
        """
    )


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO admin_permissions (
            permission_id, permission_key, label, description, sort, status, is_default, remark,
            create_time, update_time, last_time
        )
        SELECT 'perm_like', 'like', '点赞管理', '内容点赞记录管理', 45, 'enabled', true, '系统默认权限',
               CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        WHERE NOT EXISTS (SELECT 1 FROM admin_permissions WHERE permission_key = 'like')
        """
    )
    op.execute(
        """
        INSERT INTO admin_permissions (
            permission_id, permission_key, label, description, sort, status, is_default, remark,
            create_time, update_time, last_time
        )
        SELECT 'perm_share', 'share', '分享管理', '内容分享记录管理', 46, 'enabled', true, '系统默认权限',
               CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        WHERE NOT EXISTS (SELECT 1 FROM admin_permissions WHERE permission_key = 'share')
        """
    )
    op.execute(
        """
        INSERT INTO admin_menus (
            menu_id, parent_id, title, path, name, component, redirect, icon, type, permission, sort,
            status, visible, keep_alive, affix, external_link, remark, create_time, update_time, last_time
        )
        SELECT 'menu_like', NULL, '点赞管理', '/like', 'LikeList', 'views/like/List', NULL, 'Star',
               'menu', 'like', 45, 'enabled', true, false, false, NULL, '内容点赞记录管理',
               CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        WHERE NOT EXISTS (SELECT 1 FROM admin_menus WHERE menu_id = 'menu_like')
        """
    )
    op.execute(
        """
        INSERT INTO admin_menus (
            menu_id, parent_id, title, path, name, component, redirect, icon, type, permission, sort,
            status, visible, keep_alive, affix, external_link, remark, create_time, update_time, last_time
        )
        SELECT 'menu_share', NULL, '分享管理', '/share', 'ShareList', 'views/share/List', NULL, 'Share',
               'menu', 'share', 46, 'enabled', true, false, false, NULL, '内容分享记录管理',
               CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        WHERE NOT EXISTS (SELECT 1 FROM admin_menus WHERE menu_id = 'menu_share')
        """
    )

    if op.get_bind().dialect.name == "postgresql":
        _append_json_permissions("admin_roles", "role_key")
        _append_json_permissions("admin_accounts", "role")


def downgrade() -> None:
    op.execute("DELETE FROM admin_menus WHERE menu_id IN ('menu_like', 'menu_share')")
    op.execute("DELETE FROM admin_permissions WHERE permission_key IN ('like', 'share')")
