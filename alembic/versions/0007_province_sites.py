"""province sites: branding and a province on each site, and a site per province

A site (tenant) can now carry its own look and content: a slug (the first
label of its address, so mccrd.environment.gov.za and mccrd.localhost are the
same site), a short title, an emblem shown beside the DFFE logo (logo_url) and
a flag, a home page photo with its credit
(hero_image), About texts (front_matter), and colours (the existing theme
column, as CSS colour values by variable name).
A site with a province lists every project located in that province, as well
as the projects linked to it.

The national (default) site gets its full title, with "NCCRD" as its short
title, where it was only called "NCCRD": the interface shows both.

Adds a site for each of the nine provinces. The Mpumalanga site has the
title, texts and colours of the legacy MCCRD site (mccrd.environment.gov.za).
The other eight have no legacy site: they get the MCCRD's texts with their
own names and a colour from their coat of arms. Each shows its coat of arms
and a photo of a landmark of the province on its home page; the images are files of the web interface (public/sites/<slug>/).

Downgrade removes the province sites and the new columns.

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

#: The legacy MCCRD's About texts, for "{title}" and "{short_title}".
FRONT_MATTER = {
    "about": {
        "title": "Welcome to the {title}",
        "content": (
            "The platform is developed and managed by the Department of Forestry, Fisheries and the "
            "Environment (DFFE) to facilitate the monitoring and tracking of national, provincial and local "
            "responses to climate change. As outlined in both the National Development Plan (NDP) and National "
            "Climate Change Response Policy (2011), South Africa has committed to a just transition to a low "
            "carbon economy and climate-resilient society. The country is projected to face a higher frequency "
            "of climate-related disasters that are increasing in intensity, and these events are likely to be "
            "associated with impacts that are on par with, if not worse than those already experienced. The "
            "{title} ({short_title}) is intended as a resource to collect and track interventions on climate "
            "change (adaptation and mitigation) on past, current and future climate change response efforts "
            "(policies, plans, strategies, projects and research) across South Africa."
        ),
    },
    "explore": {
        "title": "Explore climate mitigation and adaptation projects",
        "content": (
            "The {short_title} is part of the National Climate Change Information System. It is designed to "
            "capture and store the details of climate change interventions including adaptation, mitigation and "
            "crosscutting efforts from across wide range of stakeholders in South Africa such as industrial "
            "entities, research, non-governmental organisations as well as government institutions and "
            "entities. Information on climate change related projects contained in the {short_title} include "
            "details mitigation and adaptation projects that features specifications on general project "
            "overview, description of funding sources and details about project supporters as well as related "
            "activity data related to the projects"
        ),
    },
    "submit": {
        "title": "Submit a project to the {title}",
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
}

#: (slug, province as the projects' locations spell it). Short titles are the
#: slug in capitals, e.g. GCCRD; Northern Cape and North West use their
#: province codes, as "NCCRD" is the national site.
PROVINCES = [
    ("eccrd", "Eastern Cape"),
    ("fccrd", "Free State"),
    ("gccrd", "Gauteng"),
    ("kccrd", "KwaZulu-Natal"),
    ("lccrd", "Limpopo"),
    ("mccrd", "Mpumalanga"),
    ("ncccrd", "Northern Cape"),
    ("nwccrd", "North West"),
    ("wccrd", "Western Cape"),
]

#: Each province's main colour, from its own symbols: the colours of its
#: provincial coat of arms (Bureau of Heraldry blazons), one shade each so no
#: two sites look alike; Mpumalanga keeps the legacy MCCRD's brown. All carry
#: white text at 7:1 or more.
COLOURS = {
    "eccrd": "#0b4f7a",   # arms: blue wavy bars, the province's coastline
    "fccrd": "#8e2459",   # arms: the Orange River lily
    "gccrd": "#6b5200",   # arms: gold pick; "place of gold"; gold on gauteng.gov.za
    "kccrd": "#0f5f5c",   # arms: green band below a blue chief
    "lccrd": "#4a5a12",   # arms: green (farming) and golden yellow (minerals)
    "mccrd": "#622700",   # the legacy MCCRD's primary colour
    "ncccrd": "#8c2d19",  # arms: red over blue
    "nwccrd": "#00653e",  # arms: the national flag's colours; its green
    "wccrd": "#1e3a8a",   # arms: blue on white
}

#: Charts take a province's second colour where it has one, else a lighter
#: step of the main colour (see _theme).
CHART_COLOURS = {
    "gccrd": "#94804a",   # gauteng.gov.za's gold
    "mccrd": "#0a51a5",   # the legacy MCCRD's secondary blue
    "ncccrd": "#2b5797",  # arms: blue
}

#: Each site's home page photo, public/sites/<slug>/hero.jpg in the web
#: interface: a landmark of the province from Wikimedia Commons, credited on
#: the page as its licence requires.
HERO_IMAGES = {
    "eccrd": {
        "credit": "Vincentvanoosten",
        "license": "CC0",
        "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
        "source_url": "https://commons.wikimedia.org/wiki/File:Hole_In_The_Wall.jpg",
    },
    "fccrd": {
        "credit": "Pavel Špindler",
        "license": "CC BY 3.0",
        "license_url": "https://creativecommons.org/licenses/by/3.0/",
        "source_url": "https://commons.wikimedia.org/wiki/File:Zebry_a_po%C5%BE%C3%A1r_v_Golden_Gate_Highlands_National_Park,_Jihoafrick%C3%A1_republika_-_panoramio.jpg",
    },
    "gccrd": {
        "credit": "Mark Hillary",
        "license": "CC BY 2.0",
        "license_url": "https://creativecommons.org/licenses/by/2.0/",
        "source_url": "https://commons.wikimedia.org/wiki/File:Johannesburg_skyline_2017.jpg",
    },
    "kccrd": {
        "credit": "PhilippN",
        "license": "CC BY-SA 3.0",
        "license_url": "https://creativecommons.org/licenses/by-sa/3.0/",
        "source_url": "https://commons.wikimedia.org/wiki/File:Amphitheatre_Drakensberg_View.jpg",
    },
    "lccrd": {
        "credit": "flowcomm",
        "license": "CC BY 2.0",
        "license_url": "https://creativecommons.org/licenses/by/2.0/",
        "source_url": "https://commons.wikimedia.org/wiki/File:Baobab_tree,_Limpopo,_South_Africa_(28585956104).jpg",
    },
    "mccrd": {
        "credit": "Dietmar Rabich",
        "license": "CC BY-SA 4.0",
        "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
        "source_url": "https://commons.wikimedia.org/wiki/File:Blyde_River_Canyon_Nature_Reserve_(ZA),_Lowveld_View,_Blyde_River_--_2024_--_9964.jpg",
    },
    "ncccrd": {
        "credit": "Svwmal",
        "license": "CC BY-SA 4.0",
        "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
        "source_url": "https://commons.wikimedia.org/wiki/File:Augrabies_Falls_oct2019.jpg",
    },
    "nwccrd": {
        "credit": "Ymblanter",
        "license": "CC BY-SA 4.0",
        "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
        "source_url": "https://commons.wikimedia.org/wiki/File:Pilanesberg_National_Park_Animals_seen_from_Pilanesberg_Centre_01.jpg",
    },
    "wccrd": {
        "credit": "Dietmar Rabich",
        "license": "CC BY-SA 4.0",
        "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
        "source_url": "https://commons.wikimedia.org/wiki/File:Cape_Town_(ZA),_Table_Mountain_--_2024_--_2794%2B96%2B98%2B2800%2B01.jpg",
    },
}


def _mix(colour: str, white: float) -> str:
    """``colour`` lightened towards white by the fraction ``white``."""
    rgb = [int(colour[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(c + (255 - c) * white):02x}" for c in rgb)


def _theme(slug: str) -> dict:
    """The colours the interface themes by, from the province's main colour."""
    primary = COLOURS[slug]
    r, g, b = (int(primary[i:i + 2], 16) for i in (1, 3, 5))
    return {
        "accent-primary": primary,
        "accent-secondary": _mix(primary, 0.12),
        "accent-green": _mix(primary, 0.22),
        "accent-light": _mix(primary, 0.4),
        "accent-surface": f"rgba({r}, {g}, {b}, 0.04)",
        "accent-border": f"rgba({r}, {g}, {b}, 0.15)",
        "chart-series": CHART_COLOURS.get(slug, _mix(primary, 0.15)),
    }


#: The province's own emblem, shown beside the DFFE logo: its coat of arms,
#: from Wikimedia Commons (CC0), or for KwaZulu-Natal and the Western Cape
#: from the provincial government's own logo (kzncogta.gov.za,
#: westerncape.gov.za). Mpumalanga, the one province with an official flag,
#: also shows it.
LOGOS = {slug: {"logo_url": f"/sites/{slug}/arms.png"} for slug, _ in PROVINCES}
LOGOS["mccrd"]["flag_url"] = "/sites/mccrd/flag.svg"


def _site(slug: str, province: str) -> dict:
    names = {"title": f"{province} Climate Change Response Database", "short_title": slug.upper()}
    return {
        "hostname": f"{slug}.environment.gov.za",
        "slug": slug,
        "province": province,
        "contact_email": "nccrd@environment.gov.za",
        "logo_url": LOGOS.get(slug, {}).get("logo_url"),
        "flag_url": LOGOS.get(slug, {}).get("flag_url"),
        "theme": json.dumps(_theme(slug)),
        "hero_image": json.dumps(dict(HERO_IMAGES[slug], url=f"/sites/{slug}/hero.jpg")),
        "front_matter": json.dumps({
            key: {field: text.format(**names) for field, text in section.items()}
            for key, section in FRONT_MATTER.items()
        }),
        **names,
    }


def upgrade() -> None:
    op.add_column("tenant", sa.Column("slug", sa.String(50)), schema="nccrd")
    op.add_column("tenant", sa.Column("short_title", sa.String(100)), schema="nccrd")
    op.add_column("tenant", sa.Column("province", sa.String(100)), schema="nccrd")
    op.add_column("tenant", sa.Column("logo_url", sa.String(500)), schema="nccrd")
    op.add_column("tenant", sa.Column("flag_url", sa.String(500)), schema="nccrd")
    op.add_column("tenant", sa.Column("front_matter", sa.JSON()), schema="nccrd")
    op.add_column("tenant", sa.Column("hero_image", sa.JSON()), schema="nccrd")
    op.create_unique_constraint("tenant_slug_key", "tenant", ["slug"], schema="nccrd")

    bind = op.get_bind()
    bind.execute(sa.text(
        "UPDATE nccrd.tenant SET short_title = 'NCCRD', title = CASE WHEN title IS NULL OR title = 'NCCRD' "
        "  THEN 'National Climate Change Response Database' ELSE title END "
        "WHERE is_default"
    ))

    for slug, province in PROVINCES:
        bind.execute(sa.text(
            "INSERT INTO nccrd.tenant (hostname, slug, title, short_title, province, logo_url, flag_url, "
            "contact_email, theme, hero_image, front_matter, is_default, include_unbounded_submissions) "
            "SELECT :hostname, :slug, :title, :short_title, :province, :logo_url, :flag_url, "
            "  :contact_email, CAST(:theme AS json), CAST(:hero_image AS json), CAST(:front_matter AS json), false, false "
            "WHERE NOT EXISTS (SELECT 1 FROM nccrd.tenant WHERE hostname = :hostname OR slug = :slug)"
        ), _site(slug, province))


def downgrade() -> None:
    op.get_bind().execute(sa.text(
        "DELETE FROM nccrd.tenant WHERE slug IN :slugs AND NOT EXISTS ("
        "  SELECT 1 FROM nccrd.tenant_xref_submission x WHERE x.tenant_id = nccrd.tenant.id) AND NOT EXISTS ("
        "  SELECT 1 FROM nccrd.user_xref_role_xref_tenant u WHERE u.tenant_id = nccrd.tenant.id)"
    ).bindparams(sa.bindparam("slugs", expanding=True)), {"slugs": [slug for slug, _ in PROVINCES]})
    op.drop_constraint("tenant_slug_key", "tenant", schema="nccrd")
    for column in ("hero_image", "front_matter", "flag_url", "logo_url", "province", "short_title", "slug"):
        op.drop_column("tenant", column, schema="nccrd")
