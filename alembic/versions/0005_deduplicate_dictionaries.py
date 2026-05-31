from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_deduplicate_dictionaries"
down_revision: str | None = "0004_dictionary_parent_id"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "select id, dict_id, parent_id, type, label, value "
            "from admin_dictionaries order by type, parent_id nulls first, id"
        )
    ).mappings().all()

    seen_labels: dict[tuple[str, str, str], str] = {}
    seen_values: dict[tuple[str, str, str], str] = {}
    duplicate_to_keep: dict[str, str] = {}
    duplicate_ids: list[int] = []

    for row in rows:
        scope = (row["type"], row["parent_id"] or "")
        label_key = (*scope, row["label"])
        value_key = (*scope, row["value"])
        keep_dict_id = seen_labels.get(label_key) or seen_values.get(value_key)
        if keep_dict_id:
            duplicate_to_keep[row["dict_id"]] = keep_dict_id
            duplicate_ids.append(row["id"])
            continue
        seen_labels[label_key] = row["dict_id"]
        seen_values[value_key] = row["dict_id"]

    for duplicate_dict_id, keep_dict_id in duplicate_to_keep.items():
        bind.execute(
            sa.text("update admin_dictionaries set parent_id = :keep_dict_id where parent_id = :duplicate_dict_id"),
            {"keep_dict_id": keep_dict_id, "duplicate_dict_id": duplicate_dict_id},
        )

    for duplicate_id in duplicate_ids:
        bind.execute(sa.text("delete from admin_dictionaries where id = :id"), {"id": duplicate_id})


def downgrade() -> None:
    pass
