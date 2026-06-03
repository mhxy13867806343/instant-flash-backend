from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017_rate_limit_access_rules"
down_revision: str | None = "0016_user_profile_bio"
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
        "admin_access_rules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("rule_id", sa.String(length=64), nullable=False),
        sa.Column("rule_type", sa.String(length=32), nullable=False),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("method", sa.String(length=16), nullable=True),
        sa.Column("path", sa.String(length=256), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("remark", sa.Text(), nullable=True),
        *timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rule_id"),
    )
    op.create_index(op.f("ix_admin_access_rules_ip"), "admin_access_rules", ["ip"], unique=False)
    op.create_index(op.f("ix_admin_access_rules_method"), "admin_access_rules", ["method"], unique=False)
    op.create_index(op.f("ix_admin_access_rules_path"), "admin_access_rules", ["path"], unique=False)
    op.create_index(op.f("ix_admin_access_rules_rule_id"), "admin_access_rules", ["rule_id"], unique=False)
    op.create_index(op.f("ix_admin_access_rules_rule_type"), "admin_access_rules", ["rule_type"], unique=False)

    op.execute(
        """
        INSERT INTO admin_permissions (
            permission_id, permission_key, label, description, sort, status, is_default, remark,
            create_time, update_time, last_time
        )
        SELECT 'perm_access_rule', 'access_rule', '黑白名单', '接口限流黑名单与白名单配置',
               170, 'enabled', true, '系统默认权限', now(), now(), now()
        WHERE NOT EXISTS (SELECT 1 FROM admin_permissions WHERE permission_key = 'access_rule')
        """
    )
    op.execute(
        """
        INSERT INTO admin_menus (
            menu_id, parent_id, title, path, name, component, redirect, icon, type, permission,
            sort, status, visible, keep_alive, affix, external_link, remark,
            create_time, update_time, last_time
        )
        SELECT 'menu_access_rule', 'menu_system', '黑白名单', 'security/access-rules', 'AccessRuleList',
               'views/security/AccessRules', NULL, 'Connection', 'menu', 'access_rule', 90, 'enabled',
               true, false, false, NULL, '接口限流黑名单与白名单配置',
               now(), now(), now()
        WHERE NOT EXISTS (SELECT 1 FROM admin_menus WHERE menu_id = 'menu_access_rule' OR name = 'AccessRuleList')
        """
    )
    op.execute(
        """
        UPDATE admin_accounts
        SET permissions = (permissions::jsonb || '["access_rule"]'::jsonb)::json
        WHERE role IN ('superadmin', 'admin')
          AND NOT (permissions::jsonb ? 'access_rule')
        """
    )
    op.execute(
        """
        UPDATE admin_roles
        SET permissions = (permissions::jsonb || '["access_rule"]'::jsonb)::json
        WHERE role_key IN ('superadmin', 'admin')
          AND NOT (permissions::jsonb ? 'access_rule')
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM admin_menus WHERE menu_id = 'menu_access_rule'")
    op.execute("DELETE FROM admin_permissions WHERE permission_id = 'perm_access_rule'")
    op.drop_index(op.f("ix_admin_access_rules_rule_type"), table_name="admin_access_rules")
    op.drop_index(op.f("ix_admin_access_rules_rule_id"), table_name="admin_access_rules")
    op.drop_index(op.f("ix_admin_access_rules_path"), table_name="admin_access_rules")
    op.drop_index(op.f("ix_admin_access_rules_method"), table_name="admin_access_rules")
    op.drop_index(op.f("ix_admin_access_rules_ip"), table_name="admin_access_rules")
    op.drop_table("admin_access_rules")
