"""add_user_password

Add password_hash and password_set_at to nccrd.user, replacing Hydra token
introspection with local password-based login. Both columns are nullable:
existing (legacy-migrated) users start with no password until activated via
the set_legacy_passwords script, and password_set_at is used as a "must
change password on next login" sentinel (NULL = never set / must change).

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        schema="nccrd",
    )
    op.add_column(
        "user",
        sa.Column("password_set_at", sa.DateTime(), nullable=True),
        schema="nccrd",
    )


def downgrade() -> None:
    op.drop_column("user", "password_set_at", schema="nccrd")
    op.drop_column("user", "password_hash", schema="nccrd")
