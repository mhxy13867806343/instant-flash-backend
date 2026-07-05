"""add user points and point records

Revision ID: 0026_user_points
Revises: 0025_feedback_management
Create Date: 2026-07-05 20:45:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0026_user_points"
down_revision = "0025_feedback_management"
branch_labels = None
depends_on = None


def _append_permission(table_name: str, role_column: str) -> None:
    op.execute(
        f"""
        UPDATE {table_name}
        SET permissions = (permissions::jsonb || '["points"]'::jsonb)::json,
            update_time = now(),
            last_time = now()
        WHERE {role_column} IN ('superadmin', 'admin')
          AND NOT (permissions::jsonb ? 'points')
        """
    )


def _remove_permission(table_name: str) -> None:
    op.execute(
        f"""
        UPDATE {table_name}
        SET permissions = (permissions::jsonb - 'points')::json,
            update_time = now(),
            last_time = now()
        WHERE permissions::jsonb ? 'points'
        """
    )


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("points", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "point_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("record_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("type", sa.Integer(), nullable=False),
        sa.Column("direction", sa.String(length=16), nullable=False, server_default="earn"),
        sa.Column("change_amount", sa.Integer(), nullable=False),
        sa.Column("balance_after", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("title", sa.String(length=128), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("source_id", sa.String(length=64), nullable=True),
        sa.Column("create_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("update_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], onupdate="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("record_id"),
    )
    op.create_index(op.f("ix_point_records_record_id"), "point_records", ["record_id"], unique=False)
    op.create_index(op.f("ix_point_records_user_id"), "point_records", ["user_id"], unique=False)
    op.create_index(op.f("ix_point_records_type"), "point_records", ["type"], unique=False)
    op.create_index(op.f("ix_point_records_source_id"), "point_records", ["source_id"], unique=False)

    op.execute(
        """
        INSERT INTO admin_permissions (
            permission_id, permission_key, label, description, sort, status, is_default, remark,
            create_time, update_time, last_time
        )
        SELECT 'perm_points', 'points', '积分管理', '用户积分列表与积分明细', 47,
               'enabled', true, '系统默认权限', now(), now(), now()
        WHERE NOT EXISTS (SELECT 1 FROM admin_permissions WHERE permission_key = 'points')
        """
    )
    op.execute(
        """
        INSERT INTO admin_menus (
            menu_id, parent_id, title, path, name, component, redirect, icon, type, permission, sort,
            status, visible, keep_alive, affix, external_link, remark, create_time, update_time, last_time
        )
        SELECT 'menu_points', NULL, '积分管理', '/points', 'PointUserList',
               'views/points/UserList', NULL, 'Coin', 'menu', 'points', 47,
               'enabled', true, false, false, NULL, '用户积分列表',
               now(), now(), now()
        WHERE NOT EXISTS (SELECT 1 FROM admin_menus WHERE menu_id = 'menu_points' OR name = 'PointUserList')
        """
    )
    op.execute(
        """
        INSERT INTO admin_menus (
            menu_id, parent_id, title, path, name, component, redirect, icon, type, permission, sort,
            status, visible, keep_alive, affix, external_link, remark, create_time, update_time, last_time
        )
        SELECT 'menu_points_records', NULL, '积分明细', '/points/\:userId/records', 'PointUserRecords',
               'views/points/UserRecords', NULL, 'Tickets', 'menu', 'points', 48,
               'enabled', false, false, false, NULL, '用户积分明细，详情路由不在侧边栏显示',
               now(), now(), now()
        WHERE NOT EXISTS (SELECT 1 FROM admin_menus WHERE menu_id = 'menu_points_records' OR name = 'PointUserRecords')
        """
    )
    _append_permission("admin_roles", "role_key")
    _append_permission("admin_accounts", "role")


def downgrade() -> None:
    op.execute("DELETE FROM admin_menus WHERE menu_id IN ('menu_points', 'menu_points_records')")
    op.execute("DELETE FROM admin_permissions WHERE permission_key = 'points'")
    _remove_permission("admin_roles")
    _remove_permission("admin_accounts")
    op.drop_index(op.f("ix_point_records_source_id"), table_name="point_records")
    op.drop_index(op.f("ix_point_records_type"), table_name="point_records")
    op.drop_index(op.f("ix_point_records_user_id"), table_name="point_records")
    op.drop_index(op.f("ix_point_records_record_id"), table_name="point_records")
    op.drop_table("point_records")
    op.drop_column("users", "points")
