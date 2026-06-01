from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0011_menu_management"
down_revision: str | None = "0010_menu_announce_perm"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ALL_PERMISSIONS = '["dashboard", "user", "content", "comment", "simulator", "account", "announcement", "version", "tag", "region", "dict", "menu", "message", "agreement"]'


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO admin_menus (
            menu_id, parent_id, title, path, name, component, redirect, icon, type,
            permission, sort, status, visible, keep_alive, affix, external_link, remark,
            create_time, update_time, last_time
        )
        VALUES (
            'menu_menu', 'menu_system', '菜单管理', '/menu', 'MenuList', 'views/menu/List',
            NULL, 'Menu', 'menu', 'menu', 40, 'enabled', true, false, false, NULL, '',
            now(), now(), now()
        )
        ON CONFLICT (menu_id) DO UPDATE SET
            parent_id = EXCLUDED.parent_id,
            title = EXCLUDED.title,
            path = EXCLUDED.path,
            name = EXCLUDED.name,
            component = EXCLUDED.component,
            icon = EXCLUDED.icon,
            type = EXCLUDED.type,
            permission = EXCLUDED.permission,
            sort = EXCLUDED.sort,
            status = EXCLUDED.status,
            visible = EXCLUDED.visible,
            update_time = now(),
            last_time = now()
        """
    )
    op.execute("UPDATE admin_menus SET sort = 50 WHERE menu_id = 'menu_message'")
    op.execute("UPDATE admin_menus SET sort = 60 WHERE menu_id = 'menu_privacy'")
    op.execute("UPDATE admin_menus SET sort = 70 WHERE menu_id = 'menu_user_agreement'")
    op.execute(f"UPDATE admin_accounts SET permissions = '{ALL_PERMISSIONS}' WHERE role = 'superadmin'")


def downgrade() -> None:
    op.execute("DELETE FROM admin_menus WHERE menu_id = 'menu_menu'")
    op.execute("UPDATE admin_menus SET sort = 40 WHERE menu_id = 'menu_message'")
    op.execute("UPDATE admin_menus SET sort = 50 WHERE menu_id = 'menu_privacy'")
    op.execute("UPDATE admin_menus SET sort = 60 WHERE menu_id = 'menu_user_agreement'")
