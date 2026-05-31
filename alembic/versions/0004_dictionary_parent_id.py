from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_dictionary_parent_id"
down_revision: str | None = "0003_system_config"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("admin_dictionaries", sa.Column("parent_id", sa.String(length=64), nullable=True))
    op.create_index(op.f("ix_admin_dictionaries_parent_id"), "admin_dictionaries", ["parent_id"], unique=False)

    bind = op.get_bind()
    rows = bind.execute(sa.text("select dict_id, type, value, remark from admin_dictionaries")).mappings().all()
    dict_id_by_type_value = {(row["type"], row["value"]): row["dict_id"] for row in rows}

    for row in rows:
        remark = row["remark"] or ""
        if not remark.startswith("parent:") or "|" not in remark:
            continue
        parent_value, clean_remark = remark[len("parent:") :].split("|", 1)
        parent_id = dict_id_by_type_value.get((row["type"], parent_value))
        if parent_id:
            bind.execute(
                sa.text("update admin_dictionaries set parent_id = :parent_id, remark = :remark where dict_id = :dict_id"),
                {"parent_id": parent_id, "remark": clean_remark, "dict_id": row["dict_id"]},
            )


def downgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(sa.text("select child.dict_id, parent.value as parent_value, child.remark from admin_dictionaries child join admin_dictionaries parent on child.parent_id = parent.dict_id")).mappings().all()
    for row in rows:
        bind.execute(
            sa.text("update admin_dictionaries set remark = :remark where dict_id = :dict_id"),
            {"remark": f"parent:{row['parent_value']}|{row['remark'] or ''}", "dict_id": row["dict_id"]},
        )

    op.drop_index(op.f("ix_admin_dictionaries_parent_id"), table_name="admin_dictionaries")
    op.drop_column("admin_dictionaries", "parent_id")
