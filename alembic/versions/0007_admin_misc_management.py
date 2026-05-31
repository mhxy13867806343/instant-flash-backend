from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_admin_misc_management"
down_revision: str | None = "0006_dictionary_unique_indexes"
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
        "admin_announcements",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("announcement_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("link", sa.String(length=512), nullable=True),
        sa.Column("pinned", sa.Boolean(), nullable=False),
        sa.Column("start_time", sa.String(length=32), nullable=True),
        sa.Column("end_time", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        *timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("announcement_id"),
    )
    op.create_index(op.f("ix_admin_announcements_announcement_id"), "admin_announcements", ["announcement_id"], unique=False)

    op.create_table(
        "admin_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("version_id", sa.String(length=64), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("build", sa.String(length=32), nullable=False),
        sa.Column("force_update", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("beta_pct", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("notes_type", sa.String(length=16), nullable=False),
        sa.Column("download_url", sa.String(length=512), nullable=True),
        sa.Column("release_time", sa.String(length=32), nullable=True),
        *timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version_id"),
    )
    op.create_index(op.f("ix_admin_versions_version_id"), "admin_versions", ["version_id"], unique=False)

    op.create_table(
        "admin_accounts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.String(length=64), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("nickname", sa.String(length=64), nullable=False),
        sa.Column("avatar", sa.String(length=512), nullable=True),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("permissions", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("email", sa.String(length=128), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("password", sa.String(length=128), nullable=False),
        sa.Column("last_login", sa.String(length=32), nullable=True),
        *timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id"),
        sa.UniqueConstraint("username"),
    )
    op.create_index(op.f("ix_admin_accounts_account_id"), "admin_accounts", ["account_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_admin_accounts_account_id"), table_name="admin_accounts")
    op.drop_table("admin_accounts")
    op.drop_index(op.f("ix_admin_versions_version_id"), table_name="admin_versions")
    op.drop_table("admin_versions")
    op.drop_index(op.f("ix_admin_announcements_announcement_id"), table_name="admin_announcements")
    op.drop_table("admin_announcements")
