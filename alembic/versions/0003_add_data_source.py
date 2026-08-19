"""add_data_source

Add a ``data_source`` column to ``nccrd.submission`` to track where each
record originated:

  * ``'sqlserver_legacy'``  — data migrated from the old SQL Server system
  * ``'react_app'``         — created via the new React frontend / API endpoint
  * ``'bulk_upload'``       — imported via the Excel bulk-upload endpoint
  * free-form label         — e.g. ``'bulk_upload: Gauteng-data-2024-01'``

Existing rows are backfilled to ``'sqlserver_legacy'``.

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "submission",
        sa.Column("data_source", sa.String(), nullable=True),
        schema="nccrd",
    )
    # Backfill — all rows that exist before this migration are legacy data.
    op.execute("UPDATE nccrd.submission SET data_source = 'sqlserver_legacy'")


def downgrade() -> None:
    op.drop_column("submission", "data_source", schema="nccrd")
