"""record the site an account was requested on

So each site's admins see, and are emailed about, the requests made on their
site. Earlier requests have none and are shown to the national site's admins.

Revision ID: 0010
Revises: 0009
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column("registration_tenant_id", sa.Integer, sa.ForeignKey("nccrd.tenant.id"), nullable=True),
        schema="nccrd",
    )


def downgrade() -> None:
    op.drop_column("user", "registration_tenant_id", schema="nccrd")
