"""index tenant_xref_submission.submission_id

Tenant scoping (`_scope_to_tenant` in nccrd/api/routers/submission.py) checks
`NOT EXISTS (... WHERE submission_id = submission.id)` for every row, and the
composite primary key (tenant_id, submission_id) can't serve a lookup on
submission_id alone, so each check was a sequential scan of the whole table.
Measured on the dev data (3,198 live submissions): one facet query 235 ms ->
8.5 ms, the unfiltered submission list query 52 ms -> 7.7 ms.

Revision ID: 0002
Revises: 0001
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "idx_tenant_xref_submission_submission_id", "tenant_xref_submission", ["submission_id"],
        schema="nccrd", postgresql_using="btree",
    )


def downgrade() -> None:
    op.drop_index("idx_tenant_xref_submission_submission_id", table_name="tenant_xref_submission", schema="nccrd")
