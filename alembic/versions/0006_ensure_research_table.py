"""ensure_research_table

nccrd.research was already defined by 0002_schema_hardening_and_multi_tenant_rbac
(op.create_table("research", ...), correctly placed in upgrade(), with a
symmetric drop_table in downgrade()). Despite that, and despite alembic_version
correctly reporting head, at least one real deployment ended up without the
table.

Root cause: this migration chain is not a from-scratch schema definition —
0001_refactor_submission_schema_v2's very first operation is
`ALTER TABLE nccrd.submission RENAME ...`, which presumes nccrd.submission
(and, it turns out, not necessarily every other table 0002 goes on to create)
already existed from some undocumented pre-alembic bootstrap step. Confirmed
directly: running `alembic upgrade head` against a genuinely empty database
fails immediately on 0001 with `relation "nccrd.submission" does not exist`.
Different environments were evidently bootstrapped from different baseline
snapshots before migration tracking began, so "alembic_version = head" does
not actually guarantee two environments have identical schemas — this
project has no single migration that can rebuild the schema from nothing.
(That's a separate, larger gap than this one table — worth its own baseline/
initial-schema migration later; out of scope here.)

This migration is intentionally guarded (checks information_schema first)
rather than a bare op.create_table: environments that already have the table
via 0002 (e.g. local dev) must see this as a no-op, not an error, while
environments missing it (confirmed: at least one deployed server) get it
created with the exact definition 0002 specifies.

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _research_table_exists(conn) -> bool:
    return conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'nccrd' AND table_name = 'research'"
        )
    ).first() is not None


def upgrade() -> None:
    conn = op.get_bind()
    if _research_table_exists(conn):
        return

    op.create_table(
        "research",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("submission_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("raw_data", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(
            ["submission_id"],
            ["nccrd.submission.id"],
            name="fk_research_submission_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="nccrd",
    )


def downgrade() -> None:
    # No-op: if this migration created the table, 0002's own downgrade()
    # already drops "research" on its way back down past this revision, so
    # dropping it again here would error. If 0002 created it (this migration
    # was a no-op going up), it's not this migration's table to drop either
    # way.
    pass
