"""add the review permissions, and give them to the sysadmin role

The review workflow checks validate-submission (the review queue, accepting
or rejecting, the data pipeline page) and counts change-submission-owner as a
curator permission. Nothing created them, though: a server set up with
deploy/scripts/bootstrap-first-user.sh has only the ten permissions that
script knew about, so nobody there could review submissions. This creates
whichever are missing and grants them to the role named "sysadmin", if there
is one. Databases that already have them, e.g. from the legacy migration, are
unaffected.

Downgrade removes nothing: the permissions may have existed before.

Revision ID: 0006
Revises: 0005
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PERMISSIONS = {
    "validate-submission": "Review submissions: accept or reject them, and see the data pipeline page.",
    "change-submission-owner": "Curate submissions owned by others.",
}


def upgrade() -> None:
    bind = op.get_bind()
    for name, description in PERMISSIONS.items():
        bind.execute(sa.text(
            "INSERT INTO nccrd.permission (name, description) SELECT :name, :description "
            "WHERE NOT EXISTS (SELECT 1 FROM nccrd.permission WHERE name = :name)"
        ), {"name": name, "description": description})
        bind.execute(sa.text(
            "INSERT INTO nccrd.permission_xref_role (permission_id, role_id) "
            "SELECT p.id, r.id FROM nccrd.permission p, nccrd.role r "
            "WHERE p.name = :name AND r.name = 'sysadmin' AND NOT EXISTS ("
            "  SELECT 1 FROM nccrd.permission_xref_role x WHERE x.permission_id = p.id AND x.role_id = r.id)"
        ), {"name": name})


def downgrade() -> None:
    pass
