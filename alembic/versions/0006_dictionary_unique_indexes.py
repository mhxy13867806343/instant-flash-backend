from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_dictionary_unique_indexes"
down_revision: str | None = "0005_deduplicate_dictionaries"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ux_admin_dictionaries_root_label",
        "admin_dictionaries",
        ["type", "label"],
        unique=True,
        postgresql_where=sa.text("parent_id is null"),
    )
    op.create_index(
        "ux_admin_dictionaries_root_value",
        "admin_dictionaries",
        ["type", "value"],
        unique=True,
        postgresql_where=sa.text("parent_id is null"),
    )
    op.create_index(
        "ux_admin_dictionaries_child_label",
        "admin_dictionaries",
        ["type", "parent_id", "label"],
        unique=True,
        postgresql_where=sa.text("parent_id is not null"),
    )
    op.create_index(
        "ux_admin_dictionaries_child_value",
        "admin_dictionaries",
        ["type", "parent_id", "value"],
        unique=True,
        postgresql_where=sa.text("parent_id is not null"),
    )


def downgrade() -> None:
    op.drop_index("ux_admin_dictionaries_child_value", table_name="admin_dictionaries")
    op.drop_index("ux_admin_dictionaries_child_label", table_name="admin_dictionaries")
    op.drop_index("ux_admin_dictionaries_root_value", table_name="admin_dictionaries")
    op.drop_index("ux_admin_dictionaries_root_label", table_name="admin_dictionaries")
