from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_system_config"
down_revision: str | None = "0002_admin_agreements"
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
        "admin_tags",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tag_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("color", sa.String(length=32), nullable=True),
        sa.Column("sort", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("remark", sa.Text(), nullable=True),
        *timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("tag_id"),
    )
    op.create_index(op.f("ix_admin_tags_tag_id"), "admin_tags", ["tag_id"], unique=False)

    op.create_table(
        "admin_regions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("region_id", sa.String(length=64), nullable=False),
        sa.Column("parent_id", sa.String(length=64), nullable=True),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("sort", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        *timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
        sa.UniqueConstraint("region_id"),
    )
    op.create_index(op.f("ix_admin_regions_parent_id"), "admin_regions", ["parent_id"], unique=False)
    op.create_index(op.f("ix_admin_regions_region_id"), "admin_regions", ["region_id"], unique=False)

    op.create_table(
        "admin_dictionaries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dict_id", sa.String(length=64), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=128), nullable=False),
        sa.Column("value", sa.String(length=128), nullable=False),
        sa.Column("sort", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("remark", sa.Text(), nullable=True),
        *timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dict_id"),
    )
    op.create_index(op.f("ix_admin_dictionaries_dict_id"), "admin_dictionaries", ["dict_id"], unique=False)
    op.create_index(op.f("ix_admin_dictionaries_type"), "admin_dictionaries", ["type"], unique=False)

    op.create_table(
        "admin_system_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("message_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("target", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("is_pinned", sa.Boolean(), nullable=False),
        *timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("message_id"),
    )
    op.create_index(
        op.f("ix_admin_system_messages_message_id"),
        "admin_system_messages",
        ["message_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_admin_system_messages_message_id"), table_name="admin_system_messages")
    op.drop_table("admin_system_messages")
    op.drop_index(op.f("ix_admin_dictionaries_type"), table_name="admin_dictionaries")
    op.drop_index(op.f("ix_admin_dictionaries_dict_id"), table_name="admin_dictionaries")
    op.drop_table("admin_dictionaries")
    op.drop_index(op.f("ix_admin_regions_region_id"), table_name="admin_regions")
    op.drop_index(op.f("ix_admin_regions_parent_id"), table_name="admin_regions")
    op.drop_table("admin_regions")
    op.drop_index(op.f("ix_admin_tags_tag_id"), table_name="admin_tags")
    op.drop_table("admin_tags")
