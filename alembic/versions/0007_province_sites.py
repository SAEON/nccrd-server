"""province sites: branding and a province on each site, and the Mpumalanga site

A site (tenant) can now carry its own look and content: a slug (the first
label of its address, so mccrd.environment.gov.za and mccrd.localhost are the
same site), a short title, a logo and flag, About texts (front_matter), and
colours (the existing theme column, as CSS colour values by variable name).
A site with a province lists every project located in that province, as well
as the projects linked to it.

The national (default) site gets its full title, with "NCCRD" as its short
title, where it was only called "NCCRD": the interface shows both.

Adds the Mpumalanga Climate Change Response Database, with the title, texts
and colours of the legacy MCCRD site (mccrd.environment.gov.za). Its logo and
flag are files of the web interface (public/sites/mccrd/).

Downgrade removes the Mpumalanga site and the new columns.

Revision ID: 0007
Revises: 0006
"""
import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MPUMALANGA = {
    "hostname": "mccrd.environment.gov.za",
    "slug": "mccrd",
    "title": "Mpumalanga Climate Change Response Database",
    "short_title": "MCCRD",
    "province": "Mpumalanga",
    "logo_url": "/sites/mccrd/logo.jpg",
    "flag_url": "/sites/mccrd/flag.jpg",
    "contact_email": "nccrd@environment.gov.za",
    # The legacy site's primary (brown) and secondary (blue) colours, with
    # shades of the brown for the interface's lighter accents.
    "theme": {
        "accent-primary": "#622700",
        "accent-secondary": "#7a3810",
        "accent-green": "#8a4a1e",
        "accent-light": "#ad6c3c",
        "accent-surface": "rgba(98, 39, 0, 0.04)",
        "accent-border": "rgba(98, 39, 0, 0.15)",
        "chart-series": "#0a51a5",
    },
    "front_matter": {
        "about": {
            "title": "Welcome to the Mpumalanga Climate Change Response Database",
            "content": (
                "The platform is developed and managed by the Department of Forestry, Fisheries and the "
                "Environment (DFFE) to facilitate the monitoring and tracking of national, provincial and local "
                "responses to climate change. As outlined in both the National Development Plan (NDP) and National "
                "Climate Change Response Policy (2011), South Africa has committed to a just transition to a low "
                "carbon economy and climate-resilient society. The country is projected to face a higher frequency "
                "of climate-related disasters that are increasing in intensity, and these events are likely to be "
                "associated with impacts that are on par with, if not worse than those already experienced. The "
                "Mpumalanga Climate Change Response Database (MCCRD) is intended as a resource to collect and track "
                "interventions on climate change (adaptation and mitigation) on past, current and future climate "
                "change response efforts (policies, plans, strategies, projects and research) across South Africa."
            ),
        },
        "explore": {
            "title": "Explore climate mitigation and adaptation projects",
            "content": (
                "The MCCRD is part of the National Climate Change Information System. It is designed to capture and "
                "store the details of climate change interventions including adaptation, mitigation and crosscutting "
                "efforts from across wide range of stakeholders in South Africa such as industrial entities, "
                "research, non-governmental organisations as well as government institutions and entities. "
                "Information on climate change related projects contained in the MCCRD include details mitigation "
                "and adaptation projects that features specifications on general project overview, description of "
                "funding sources and details about project supporters as well as related activity data related to "
                "the projects"
            ),
        },
        "submit": {
            "title": "Submit a project to the Mpumalanga Climate Change Response Database",
            "content": (
                "Although the submission of information to the database is voluntary, data providers are encouraged "
                "to upload and update the information into the database to benefit a wide range of use cases in the "
                "country. While the administrator of the database (DFFE) takes all necessary steps to ensure quality "
                "of captured data, users of the information should note that accuracy of the information captured "
                "herein cannot be guaranteed. The database presents a platform where Project managers can upload "
                "information on their projects’ details as well as to provide periodic updates. The database is "
                "beneficial in supporting various use cases in support of the National Climate Change Policy (2011) "
                "imperatives. The submitted data supports the undertaking of climate change monitoring and "
                "evaluation to track South Africa’s transition to a lower carbon economy and climate resilient "
                "society."
            ),
        },
    },
}


def upgrade() -> None:
    op.add_column("tenant", sa.Column("slug", sa.String(50)), schema="nccrd")
    op.add_column("tenant", sa.Column("short_title", sa.String(100)), schema="nccrd")
    op.add_column("tenant", sa.Column("province", sa.String(100)), schema="nccrd")
    op.add_column("tenant", sa.Column("logo_url", sa.String(500)), schema="nccrd")
    op.add_column("tenant", sa.Column("flag_url", sa.String(500)), schema="nccrd")
    op.add_column("tenant", sa.Column("front_matter", sa.JSON()), schema="nccrd")
    op.create_unique_constraint("tenant_slug_key", "tenant", ["slug"], schema="nccrd")

    op.get_bind().execute(sa.text(
        "UPDATE nccrd.tenant SET short_title = 'NCCRD', title = 'National Climate Change Response Database' "
        "WHERE is_default AND (title IS NULL OR title = 'NCCRD')"
    ))

    site = dict(MPUMALANGA, theme=json.dumps(MPUMALANGA["theme"]), front_matter=json.dumps(MPUMALANGA["front_matter"]))
    op.get_bind().execute(sa.text(
        "INSERT INTO nccrd.tenant (hostname, slug, title, short_title, province, logo_url, flag_url, "
        "contact_email, theme, front_matter, is_default, include_unbounded_submissions) "
        "SELECT :hostname, :slug, :title, :short_title, :province, :logo_url, :flag_url, "
        "  :contact_email, CAST(:theme AS json), CAST(:front_matter AS json), false, false "
        "WHERE NOT EXISTS (SELECT 1 FROM nccrd.tenant WHERE hostname = :hostname OR slug = :slug)"
    ), site)


def downgrade() -> None:
    op.get_bind().execute(sa.text(
        "DELETE FROM nccrd.tenant WHERE slug = 'mccrd' AND NOT EXISTS ("
        "  SELECT 1 FROM nccrd.tenant_xref_submission x WHERE x.tenant_id = nccrd.tenant.id) AND NOT EXISTS ("
        "  SELECT 1 FROM nccrd.user_xref_role_xref_tenant u WHERE u.tenant_id = nccrd.tenant.id)"
    ))
    op.drop_constraint("tenant_slug_key", "tenant", schema="nccrd")
    for column in ("front_matter", "flag_url", "logo_url", "province", "short_title", "slug"):
        op.drop_column("tenant", column, schema="nccrd")
