"""submission_updatedby_deletedby_fk

Add FK constraints on nccrd.submission.updatedby and nccrd.submission.deletedby
referencing nccrd.user.id. Migration 0002 only wired up createdby and
submission_status_updated_by, leaving updatedby/deletedby orphaned integers.

Backfills nccrd.user with placeholder rows for any updatedby/deletedby values
that don't already have a corresponding user (same pattern as 0002's createdby
backfill) before adding the constraints, so the migration doesn't fail on
legacy data.

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO nccrd.user (id, uuid, name, email, deleted)
        SELECT DISTINCT v.uid,
               gen_random_uuid(),
               'Legacy User ' || v.uid,
               'legacy_user_' || v.uid || '@placeholder.local',
               false
        FROM (
            SELECT updatedby AS uid FROM nccrd.submission WHERE updatedby IS NOT NULL
            UNION
            SELECT deletedby AS uid FROM nccrd.submission WHERE deletedby IS NOT NULL
        ) v
        ON CONFLICT (id) DO NOTHING
    """)

    op.create_foreign_key(
        "fk_submission_updatedby",
        "submission",
        "user",
        ["updatedby"],
        ["id"],
        source_schema="nccrd",
        referent_schema="nccrd",
    )

    op.create_foreign_key(
        "fk_submission_deletedby",
        "submission",
        "user",
        ["deletedby"],
        ["id"],
        source_schema="nccrd",
        referent_schema="nccrd",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_submission_deletedby",
        "submission",
        schema="nccrd",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_submission_updatedby",
        "submission",
        schema="nccrd",
        type_="foreignkey",
    )
