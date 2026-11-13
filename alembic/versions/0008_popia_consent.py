"""record POPIA consent: privacy notice on sign-up, project manager contacts

user.privacy_notice_accepted_at: when a person accepted the privacy notice
on signing up (POST /auth/register now requires it). NULL for admin-created
and legacy accounts.

submission.contact_consent_at: when the submitter confirmed the project
manager agreed to their contact details being held for the project (the app
now requires it whenever contact details are given or changed). NULL for
legacy and register imports.

Revision ID: 0008
Revises: 0007
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user", sa.Column("privacy_notice_accepted_at", sa.DateTime()), schema="nccrd")
    op.add_column("submission", sa.Column("contact_consent_at", sa.DateTime()), schema="nccrd")


def downgrade() -> None:
    op.drop_column("submission", "contact_consent_at", schema="nccrd")
    op.drop_column("user", "privacy_notice_accepted_at", schema="nccrd")
