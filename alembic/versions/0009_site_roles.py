"""add the contributor, reviewer and site-admin roles, and the edit-site permission

Until now a server had one role, sysadmin, so approving an account request
(which offers the roles there are) made the person a sysadmin. These roles
let an admin give each person what they need, on one site:

* contributor: submit projects, upload the workbook, attach files.
* reviewer: also edit any project and accept or send back submissions.
* site-admin: also delete projects, manage people's roles on the site, and
  edit the site's texts and branding.

edit-site, the last of those, is new: sysadmin gets it too. Roles that
already exist by these names keep their permissions; only missing links are
added.

Downgrade removes nothing: people may already hold these roles.

Revision ID: 0009
Revises: 0008
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PERMISSIONS = {
    "create-submission": "Submit projects.",
    "upload-template": "Submit projects with the bulk-upload workbook.",
    "attach-file-to-submission": "Attach files, e.g. progress reports, to a project.",
    "update-submission": "Edit any project.",
    "validate-submission": "Review submissions: accept or reject them, and see the data pipeline page.",
    "delete-submission": "Delete projects.",
    "assign-role": "Approve account requests and manage people's roles.",
    "view-users": "See the people with accounts.",
    "view-roles": "See the roles.",
    "view-tenants": "See the sites.",
    "edit-site": "Edit the site's texts, contact address and branding.",
}

_CONTRIBUTOR = ["create-submission", "upload-template", "attach-file-to-submission"]
_REVIEWER = _CONTRIBUTOR + ["update-submission", "validate-submission"]
_SITE_ADMIN = _REVIEWER + ["delete-submission", "assign-role", "view-users", "view-roles", "view-tenants", "edit-site"]

ROLES = {
    "contributor": ("Submits projects to the site.", _CONTRIBUTOR),
    "reviewer": ("Reviews and edits the site's projects, and submits their own.", _REVIEWER),
    "site-admin": ("Runs the site: reviews projects, manages people's roles, edits the site's texts.", _SITE_ADMIN),
    "sysadmin": (None, ["edit-site"]),  # has the rest already
}


def upgrade() -> None:
    bind = op.get_bind()
    for name, description in PERMISSIONS.items():
        bind.execute(sa.text(
            "INSERT INTO nccrd.permission (name, description) SELECT :name, :description "
            "WHERE NOT EXISTS (SELECT 1 FROM nccrd.permission WHERE name = :name)"
        ), {"name": name, "description": description})

    for role, (description, permissions) in ROLES.items():
        if description is not None:
            bind.execute(sa.text(
                "INSERT INTO nccrd.role (name, description) SELECT :role, :description "
                "WHERE NOT EXISTS (SELECT 1 FROM nccrd.role WHERE name = :role)"
            ), {"role": role, "description": description})
        for permission in permissions:
            bind.execute(sa.text(
                "INSERT INTO nccrd.permission_xref_role (permission_id, role_id) "
                "SELECT p.id, r.id FROM nccrd.permission p, nccrd.role r "
                "WHERE p.name = :permission AND r.name = :role AND NOT EXISTS ("
                "  SELECT 1 FROM nccrd.permission_xref_role x WHERE x.permission_id = p.id AND x.role_id = r.id)"
            ), {"permission": permission, "role": role})


def downgrade() -> None:
    pass
