from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_admin_menus"
down_revision: str | None = "0007_admin_misc_management"
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
        "admin_menus",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("menu_id", sa.String(length=64), nullable=False),
        sa.Column("parent_id", sa.String(length=64), nullable=True),
        sa.Column("title", sa.String(length=64), nullable=False),
        sa.Column("path", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("component", sa.String(length=128), nullable=True),
        sa.Column("redirect", sa.String(length=128), nullable=True),
        sa.Column("icon", sa.String(length=64), nullable=True),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("permission", sa.String(length=64), nullable=True),
        sa.Column("sort", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("visible", sa.Boolean(), nullable=False),
        sa.Column("keep_alive", sa.Boolean(), nullable=False),
        sa.Column("affix", sa.Boolean(), nullable=False),
        sa.Column("external_link", sa.String(length=512), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        *timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("menu_id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_admin_menus_menu_id"), "admin_menus", ["menu_id"], unique=False)
    op.create_index(op.f("ix_admin_menus_parent_id"), "admin_menus", ["parent_id"], unique=False)
    op.create_index(op.f("ix_admin_menus_permission"), "admin_menus", ["permission"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_admin_menus_permission"), table_name="admin_menus")
    op.drop_index(op.f("ix_admin_menus_parent_id"), table_name="admin_menus")
    op.drop_index(op.f("ix_admin_menus_menu_id"), table_name="admin_menus")
    op.drop_table("admin_menus")
