from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_admin_packages"
down_revision: str | None = "0014_admin_security_logs"
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
        "admin_packages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("package_id", sa.String(length=64), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("build", sa.String(length=32), nullable=True),
        sa.Column("display_name", sa.String(length=256), nullable=False),
        sa.Column("original_filename", sa.String(length=256), nullable=False),
        sa.Column("file_path", sa.String(length=512), nullable=False),
        sa.Column("download_url", sa.String(length=512), nullable=False),
        sa.Column("md5", sa.String(length=32), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("remark", sa.Text(), nullable=True),
        *timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("package_id"),
    )
    op.create_index(op.f("ix_admin_packages_md5"), "admin_packages", ["md5"], unique=False)
    op.create_index(op.f("ix_admin_packages_package_id"), "admin_packages", ["package_id"], unique=False)
    op.create_index(op.f("ix_admin_packages_platform"), "admin_packages", ["platform"], unique=False)
    op.create_index(op.f("ix_admin_packages_version"), "admin_packages", ["version"], unique=False)

    op.execute(
        """
        INSERT INTO admin_menus (
            menu_id, parent_id, title, path, name, component, redirect, icon, type, permission,
            sort, status, visible, keep_alive, affix, external_link, remark,
            create_time, update_time, last_time
        )
        SELECT 'menu_version_packages', NULL, '安装包管理', '/version/packages', 'VersionPackageUpload',
               'views/version/Packages', NULL, 'UploadFilled', 'menu', 'version', 81, 'enabled',
               true, false, false, NULL, 'Android/iOS/HarmonyOS 安装包上传与历史记录',
               now(), now(), now()
        WHERE NOT EXISTS (SELECT 1 FROM admin_menus WHERE menu_id = 'menu_version_packages' OR name = 'VersionPackageUpload')
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM admin_menus WHERE menu_id = 'menu_version_packages'")
    op.drop_index(op.f("ix_admin_packages_version"), table_name="admin_packages")
    op.drop_index(op.f("ix_admin_packages_platform"), table_name="admin_packages")
    op.drop_index(op.f("ix_admin_packages_package_id"), table_name="admin_packages")
    op.drop_index(op.f("ix_admin_packages_md5"), table_name="admin_packages")
    op.drop_table("admin_packages")
