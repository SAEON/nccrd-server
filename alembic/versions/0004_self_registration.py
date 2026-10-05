"""self sign-up: registration status, organisation and note on user

POST /auth/register creates an account with registration_status "pending";
an admin approves it (granting a role) or rejects it. Admin-created and legacy
accounts keep NULL and are unaffected.

Revision ID: 0004
Revises: 0003
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user", sa.Column("registration_status", sa.String(20)), schema="nccrd")
    op.add_column("user", sa.Column("organisation", sa.String(500)), schema="nccrd")
    op.add_column("user", sa.Column("registration_note", sa.Text()), schema="nccrd")


def downgrade() -> None:
    op.drop_column("user", "registration_note", schema="nccrd")
    op.drop_column("user", "organisation", schema="nccrd")
    op.drop_column("user", "registration_status", schema="nccrd")
