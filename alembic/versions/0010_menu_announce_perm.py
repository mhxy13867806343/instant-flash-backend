from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0010_menu_announce_perm"
down_revision: str | None = "0009_fix_menu_permissions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("UPDATE admin_menus SET permission = 'announcement' WHERE menu_id IN ('menu_announcement', 'menu_announcement_single', 'menu_announcement_list')")


def downgrade() -> None:
    op.execute("UPDATE admin_menus SET permission = 'agreement' WHERE menu_id IN ('menu_announcement', 'menu_announcement_single', 'menu_announcement_list')")
