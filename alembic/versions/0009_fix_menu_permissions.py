from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0009_fix_menu_permissions"
down_revision: str | None = "0008_admin_menus"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("UPDATE admin_menus SET permission = 'simulator' WHERE menu_id = 'menu_simulator'")
    op.execute("UPDATE admin_menus SET permission = 'version' WHERE menu_id = 'menu_version'")


def downgrade() -> None:
    op.execute("UPDATE admin_menus SET permission = 'dashboard' WHERE menu_id = 'menu_simulator'")
    op.execute("UPDATE admin_menus SET permission = 'dashboard' WHERE menu_id = 'menu_version'")
