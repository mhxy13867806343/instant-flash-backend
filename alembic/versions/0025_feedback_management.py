"""add feedback management

Revision ID: 0025_feedback_management
Revises: 0024_post_topics
Create Date: 2026-06-04 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0025_feedback_management"
down_revision = "0024_post_topics"
branch_labels = None
depends_on = None


def _append_permission(table_name: str, role_column: str) -> None:
    op.execute(
        f"""
        UPDATE {table_name}
        SET permissions = (permissions::jsonb || '["feedback"]'::jsonb)::json,
            update_time = now(),
            last_time = now()
        WHERE {role_column} IN ('superadmin', 'admin')
          AND NOT (permissions::jsonb ? 'feedback')
        """
    )


def _remove_permission(table_name: str) -> None:
    op.execute(
        f"""
        UPDATE {table_name}
        SET permissions = (permissions::jsonb - 'feedback')::json,
            update_time = now(),
            last_time = now()
        WHERE permissions::jsonb ? 'feedback'
        """
    )


def upgrade() -> None:
    op.create_table(
        "admin_feedback_form_configs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("config_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=128), nullable=False, server_default="意见反馈"),
        sa.Column("menu_title", sa.String(length=128), nullable=False, server_default="反馈管理"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("submit_button_text", sa.String(length=64), nullable=False, server_default="提交反馈"),
        sa.Column("success_message", sa.String(length=128), nullable=False, server_default="反馈提交成功"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="enabled"),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("create_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("update_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("config_id"),
    )
    op.create_index(op.f("ix_admin_feedback_form_configs_config_id"), "admin_feedback_form_configs", ["config_id"], unique=False)

    op.create_table(
        "admin_feedback_fields",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("field_id", sa.String(length=64), nullable=False),
        sa.Column("form_id", sa.String(length=64), nullable=False),
        sa.Column("field_key", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=128), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False, server_default="input"),
        sa.Column("placeholder", sa.String(length=256), nullable=True),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("options", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("sort", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="enabled"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("create_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("update_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("field_id"),
    )
    op.create_index(op.f("ix_admin_feedback_fields_field_id"), "admin_feedback_fields", ["field_id"], unique=False)
    op.create_index(op.f("ix_admin_feedback_fields_field_key"), "admin_feedback_fields", ["field_key"], unique=False)
    op.create_index(op.f("ix_admin_feedback_fields_form_id"), "admin_feedback_fields", ["form_id"], unique=False)

    op.create_table(
        "feedback_submissions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("feedback_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("title", sa.String(length=128), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("reply", sa.Text(), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("create_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("update_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("feedback_id"),
    )
    op.create_index(op.f("ix_feedback_submissions_feedback_id"), "feedback_submissions", ["feedback_id"], unique=False)
    op.create_index(op.f("ix_feedback_submissions_phone"), "feedback_submissions", ["phone"], unique=False)
    op.create_index(op.f("ix_feedback_submissions_title"), "feedback_submissions", ["title"], unique=False)
    op.create_index(op.f("ix_feedback_submissions_user_id"), "feedback_submissions", ["user_id"], unique=False)

    op.execute(
        """
        INSERT INTO admin_feedback_form_configs (
            config_id, title, menu_title, description, submit_button_text, success_message,
            status, remark, create_time, update_time, last_time
        )
        VALUES (
            'default', '意见反馈', '反馈管理', '请填写手机号码、标题和反馈内容，我们会尽快处理。',
            '提交反馈', '反馈提交成功', 'enabled', '系统默认反馈表单', now(), now(), now()
        )
        ON CONFLICT (config_id) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO admin_feedback_fields (
            field_id, form_id, field_key, label, type, placeholder, required, options, sort,
            status, is_default, remark, create_time, update_time, last_time
        )
        VALUES
            ('fb_field_phone', 'default', 'phone', '手机号码', 'phone', '请填写手机号码', true, '[]', 10, 'enabled', true, '系统默认反馈字段', now(), now(), now()),
            ('fb_field_title', 'default', 'title', '反馈标题', 'input', '请输入标题或菜单名称', true, '[]', 20, 'enabled', true, '系统默认反馈字段', now(), now(), now()),
            ('fb_field_content', 'default', 'content', '反馈内容', 'textarea', '请填写具体反馈内容', true, '[]', 30, 'enabled', true, '系统默认反馈字段', now(), now(), now())
        ON CONFLICT (field_id) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO admin_permissions (
            permission_id, permission_key, label, description, sort, status, is_default, remark,
            create_time, update_time, last_time
        )
        SELECT 'perm_feedback', 'feedback', '反馈管理', '配置用户端反馈动态表单并处理反馈', 190,
               'enabled', true, '系统默认权限', now(), now(), now()
        WHERE NOT EXISTS (SELECT 1 FROM admin_permissions WHERE permission_key = 'feedback')
        """
    )
    op.execute(
        """
        INSERT INTO admin_menus (
            menu_id, parent_id, title, path, name, component, redirect, icon, type, permission, sort,
            status, visible, keep_alive, affix, external_link, remark, create_time, update_time, last_time
        )
        SELECT 'menu_feedback', 'menu_system', '反馈管理', 'feedback', 'FeedbackManage',
               'views/feedback/List', NULL, 'ChatDotRound', 'menu', 'feedback', 110,
               'enabled', true, false, false, NULL, '系统配置 - 反馈动态表单和反馈记录管理',
               now(), now(), now()
        WHERE NOT EXISTS (SELECT 1 FROM admin_menus WHERE menu_id = 'menu_feedback' OR name = 'FeedbackManage')
        """
    )
    _append_permission("admin_roles", "role_key")
    _append_permission("admin_accounts", "role")


def downgrade() -> None:
    op.execute("DELETE FROM admin_menus WHERE menu_id = 'menu_feedback'")
    op.execute("DELETE FROM admin_permissions WHERE permission_key = 'feedback'")
    _remove_permission("admin_roles")
    _remove_permission("admin_accounts")
    op.drop_index(op.f("ix_feedback_submissions_user_id"), table_name="feedback_submissions")
    op.drop_index(op.f("ix_feedback_submissions_title"), table_name="feedback_submissions")
    op.drop_index(op.f("ix_feedback_submissions_phone"), table_name="feedback_submissions")
    op.drop_index(op.f("ix_feedback_submissions_feedback_id"), table_name="feedback_submissions")
    op.drop_table("feedback_submissions")
    op.drop_index(op.f("ix_admin_feedback_fields_form_id"), table_name="admin_feedback_fields")
    op.drop_index(op.f("ix_admin_feedback_fields_field_key"), table_name="admin_feedback_fields")
    op.drop_index(op.f("ix_admin_feedback_fields_field_id"), table_name="admin_feedback_fields")
    op.drop_table("admin_feedback_fields")
    op.drop_index(op.f("ix_admin_feedback_form_configs_config_id"), table_name="admin_feedback_form_configs")
    op.drop_table("admin_feedback_form_configs")
