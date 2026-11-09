"""count page views per site and day, and record each download's site

page_view holds one row per site, day and page, with the number of views:
no visitor is identified, no IP address or cookie is kept. download_log gets
the site the download was made on (earlier ones have none). The view-stats
permission, to see these numbers, goes to site-admin and sysadmin.

Revision ID: 0011
Revises: 0010
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "page_view",
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("nccrd.tenant.id"), primary_key=True),
        sa.Column("day", sa.Date, primary_key=True),
        sa.Column("path", sa.String(200), primary_key=True),
        sa.Column("views", sa.Integer, nullable=False, server_default="0"),
        schema="nccrd",
    )
    op.add_column(
        "download_log",
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("nccrd.tenant.id"), nullable=True),
        schema="nccrd",
    )
    bind = op.get_bind()
    bind.execute(sa.text(
        "INSERT INTO nccrd.permission (name, description) SELECT 'view-stats', "
        "'See the site''s visitor numbers and downloads.' "
        "WHERE NOT EXISTS (SELECT 1 FROM nccrd.permission WHERE name = 'view-stats')"
    ))
    bind.execute(sa.text(
        "INSERT INTO nccrd.permission_xref_role (permission_id, role_id) "
        "SELECT p.id, r.id FROM nccrd.permission p, nccrd.role r "
        "WHERE p.name = 'view-stats' AND r.name IN ('site-admin', 'sysadmin') AND NOT EXISTS ("
        "  SELECT 1 FROM nccrd.permission_xref_role x WHERE x.permission_id = p.id AND x.role_id = r.id)"
    ))


def downgrade() -> None:
    op.drop_column("download_log", "tenant_id", schema="nccrd")
    op.drop_table("page_view", schema="nccrd")
