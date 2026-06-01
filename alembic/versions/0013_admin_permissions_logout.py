from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_admin_permissions_logout"
down_revision: str | None = "0012_admin_roles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_PERMISSIONS = [
    ("perm_dashboard", "dashboard", "数据看板", "后台首页数据看板", 10),
    ("perm_user", "user", "用户管理", "用户列表、禁用和详情", 20),
    ("perm_content", "content", "内容管理", "动态内容审核与上下架", 30),
    ("perm_comment", "comment", "评论管理", "评论列表与删除", 40),
    ("perm_simulator", "simulator", "App 仿真模拟", "App 仿真模拟页面", 50),
    ("perm_account", "account", "账号管理", "后台账号和角色配置", 60),
    ("perm_announcement", "announcement", "公告管理", "单公告和公告列表", 70),
    ("perm_version", "version", "版本管理", "App 版本管理", 80),
    ("perm_system", "system", "系统配置", "系统配置目录权限", 90),
    ("perm_tag", "tag", "标签管理", "动态标签配置", 100),
    ("perm_region", "region", "地区管理", "地区和定位配置", 110),
    ("perm_dict", "dict", "字典管理", "业务字典配置", 120),
    ("perm_menu", "menu", "菜单管理", "后台动态菜单配置", 130),
    ("perm_message", "message", "系统消息", "系统消息推送", 140),
    ("perm_agreement", "agreement", "协议管理", "用户协议和隐私协议", 150),
]


def timestamp_columns() -> list[sa.Column]:
    return [
        sa.Column("create_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("update_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_time", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "admin_permissions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("permission_id", sa.String(length=64), nullable=False),
        sa.Column("permission_key", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=64), nullable=False),
        sa.Column("description", sa.String(length=256), nullable=True),
        sa.Column("sort", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("remark", sa.Text(), nullable=True),
        *timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("permission_id"),
        sa.UniqueConstraint("permission_key"),
    )
    op.create_index(op.f("ix_admin_permissions_permission_id"), "admin_permissions", ["permission_id"], unique=False)

    values = ",\n".join(
        f"('{permission_id}', '{permission_key}', '{label}', '{description}', {sort}, 'enabled', true, '系统默认权限', now(), now(), now())"
        for permission_id, permission_key, label, description, sort in DEFAULT_PERMISSIONS
    )
    op.execute(
        f"""
        INSERT INTO admin_permissions (
            permission_id, permission_key, label, description, sort, status, is_default, remark,
            create_time, update_time, last_time
        )
        VALUES
            {values}
        """
    )
    op.execute(
        """
        UPDATE admin_accounts
        SET permissions = (permissions::jsonb || '["system"]'::jsonb)::json
        WHERE role = 'superadmin'
          AND NOT (permissions::jsonb ? 'system')
        """
    )
    op.execute(
        """
        UPDATE admin_roles
        SET permissions = (permissions::jsonb || '["system"]'::jsonb)::json
        WHERE role_key = 'superadmin'
          AND NOT (permissions::jsonb ? 'system')
        """
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_admin_permissions_permission_id"), table_name="admin_permissions")
    op.drop_table("admin_permissions")
