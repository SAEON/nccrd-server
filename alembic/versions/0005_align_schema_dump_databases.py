"""bring databases loaded from a schema dump in line with the baseline

The development server's schema was loaded from a schema dump of an older
local database (deploy/server-schema-only.sql) and stamped, not built by
0001. That dump differs from what 0001 creates and the models declare, so
`alembic check` reports it:

- five unique constraints are missing, so nothing stops duplicate rows in
  these link tables;
- progress_report's foreign key to submission lacks ON DELETE CASCADE, and
  has the name Postgres generates instead of 0001's.

This fixes each only where it differs, so databases built by the migrations
are unaffected.

Downgrade does nothing: on databases built by 0001 these are part of the
baseline, and there is no telling which ones this migration changed.

Revision ID: 0005
Revises: 0004
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: (table, constraint name as in 0001, columns)
CONSTRAINTS = [
    ("tree", "tree_name_key", ["name"]),
    ("vocabulary_xref_tree", "vocabulary_xref_tree_vocabulary_id_tree_id_key", ["vocabulary_id", "tree_id"]),
    ("vocabulary_xref_vocabulary", "vocabulary_xref_vocabulary_child_id_tree_id_key", ["child_id", "tree_id"]),
    ("permission_xref_role", "permission_xref_role_permission_id_role_id_key", ["permission_id", "role_id"]),
    ("user_xref_role_xref_tenant", "user_xref_role_xref_tenant_user_id_role_id_tenant_id_key",
     ["user_id", "role_id", "tenant_id"]),
]


def _exists(bind, name: str) -> bool:
    return bool(bind.execute(sa.text(
        "SELECT 1 FROM pg_constraint WHERE conname = :name AND connamespace = 'nccrd'::regnamespace"
    ), {"name": name}).scalar())


def upgrade() -> None:
    bind = op.get_bind()
    for table, name, columns in CONSTRAINTS:
        if not _exists(bind, name):
            op.create_unique_constraint(name, table, columns, schema="nccrd")

    if not _exists(bind, "fk_progress_report_submission_id"):
        if _exists(bind, "progress_report_submission_id_fkey"):
            op.drop_constraint("progress_report_submission_id_fkey", "progress_report", schema="nccrd",
                               type_="foreignkey")
        op.create_foreign_key("fk_progress_report_submission_id", "progress_report", "submission",
                              ["submission_id"], ["id"], source_schema="nccrd", referent_schema="nccrd",
                              ondelete="CASCADE")


def downgrade() -> None:
    pass
