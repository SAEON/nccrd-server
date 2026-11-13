import hashlib
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from nccrd.api.lib.auth import Authorized
from nccrd.api.lib.permissions import RequirePermission
from nccrd.api.lib.tenant import get_current_tenant
from nccrd.api.models.rbac import SITE_SECTIONS, SiteResponse, SiteUpdate
from nccrd.db import get_db
from nccrd.db.models.rbac import Tenant

router = APIRouter()

EDIT_SITE = "edit-site"

#: Site images people upload: the emblem, the flag and the front-page photo.
#: Served at /uploads/sites, from the uploads volume that outlives redeploys.
SITE_UPLOAD_DIR = Path(__file__).resolve().parents[3] / "uploads" / "sites"
SITE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
SITE_UPLOAD_URL = "/uploads/sites"
MAX_SITE_IMAGE_BYTES = 3 * 1024 * 1024

#: Raster images only, known by their first bytes. Not SVG: it can carry scripts.
_IMAGE_TYPES = {
    b"\x89PNG\r\n\x1a\n": ".png",
    b"\xff\xd8\xff": ".jpg",
}

ImageKind = Literal["logo", "flag", "hero"]


def _image_extension(data: bytes):
    for magic, extension in _IMAGE_TYPES.items():
        if data.startswith(magic):
            return extension
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    return None


def _mix(colour: str, white: float) -> str:
    """``colour`` lightened towards white by the fraction ``white``."""
    rgb = [int(colour[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(c + (255 - c) * white):02x}" for c in rgb)


def theme_from_colour(primary: str, chart_series: str = None) -> dict:
    """The colours the interface themes by, from the site's main colour (as migration 0007 made them)."""
    primary = primary.lower()
    r, g, b = (int(primary[i:i + 2], 16) for i in (1, 3, 5))
    return {
        "accent-primary": primary,
        "accent-secondary": _mix(primary, 0.12),
        "accent-green": _mix(primary, 0.22),
        "accent-light": _mix(primary, 0.4),
        "accent-surface": f"rgba({r}, {g}, {b}, 0.04)",
        "accent-border": f"rgba({r}, {g}, {b}, 0.15)",
        "chart-series": chart_series or _mix(primary, 0.15),
    }


@router.get(
    "",
    response_model=SiteResponse,
    summary="Return the current site's names, province and branding.",
)
def get_site(tenant: Tenant = Depends(get_current_tenant)) -> SiteResponse:
    """
    The site (tenant) the request is for, e.g. the national NCCRD or the
    Mpumalanga MCCRD, with what the web interface shows for it: titles, logo,
    flag, colours and About texts. Public, as every page needs it.
    """
    return SiteResponse.model_validate(tenant)


@router.put(
    "",
    response_model=SiteResponse,
    summary="Change the current site's names, contact address, colour, About texts or photo credit.",
)
def update_site(
        body: SiteUpdate,
        db: Session = Depends(get_db),
        tenant: Tenant = Depends(get_current_tenant),
        auth: Authorized = Depends(RequirePermission(EDIT_SITE)),
) -> SiteResponse:
    if body.title is not None:
        tenant.title = body.title.strip()
    if body.short_title is not None:
        tenant.short_title = body.short_title.strip()
    if body.contact_email is not None:
        tenant.contact_email = body.contact_email.strip()
    if body.colour is not None:
        # Keep a chart colour chosen to stand apart from the main one.
        tenant.theme = theme_from_colour(body.colour, (tenant.theme or {}).get("chart-series"))
    if body.sections is not None:
        unknown = set(body.sections) - set(SITE_SECTIONS)
        if unknown:
            raise HTTPException(status_code=422, detail=f"Unknown section: {', '.join(sorted(unknown))}.")
        sections = dict(tenant.front_matter or {})
        for key, section in body.sections.items():
            sections[key] = {"title": section.title.strip(), "content": section.content.strip()}
        tenant.front_matter = sections
    if body.hero_credit is not None:
        hero = dict(tenant.hero_image or {})
        hero.update({k: (v.strip() or None) if isinstance(v, str) else v for k, v in body.hero_credit.model_dump().items()})
        tenant.hero_image = hero
    db.commit()
    db.refresh(tenant)
    return SiteResponse.model_validate(tenant)


def _set_image(tenant: Tenant, kind: str, url):
    if kind == "hero":
        hero = dict(tenant.hero_image or {})
        if url is None:
            # Back to the default photo, whose credit no longer applies.
            tenant.hero_image = None
        else:
            hero["url"] = url
            tenant.hero_image = hero
    else:
        setattr(tenant, f"{kind}_url", url)


@router.post(
    "/images/{kind}",
    response_model=SiteResponse,
    summary="Upload the site's emblem (logo), flag or front-page photo (hero): PNG, JPEG or WebP, up to 3 MB.",
)
async def upload_site_image(
        kind: ImageKind,
        file: UploadFile = File(...),
        db: Session = Depends(get_db),
        tenant: Tenant = Depends(get_current_tenant),
        auth: Authorized = Depends(RequirePermission(EDIT_SITE)),
) -> SiteResponse:
    data = await file.read(MAX_SITE_IMAGE_BYTES + 1)
    if len(data) > MAX_SITE_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="The image is larger than 3 MB.")
    extension = _image_extension(data)
    if extension is None:
        raise HTTPException(status_code=422, detail="Upload a PNG, JPEG or WebP image.")

    # Named by content, so a changed image gets a new address and no browser shows an old copy.
    name = f"{kind}-{hashlib.sha256(data).hexdigest()[:16]}{extension}"
    folder = SITE_UPLOAD_DIR / str(tenant.id)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_bytes(data)

    _set_image(tenant, kind, f"{SITE_UPLOAD_URL}/{tenant.id}/{name}")
    db.commit()
    db.refresh(tenant)
    return SiteResponse.model_validate(tenant)


@router.delete(
    "/images/{kind}",
    response_model=SiteResponse,
    summary="Remove the site's emblem or flag, or go back to the default front-page photo.",
)
def remove_site_image(
        kind: ImageKind,
        db: Session = Depends(get_db),
        tenant: Tenant = Depends(get_current_tenant),
        auth: Authorized = Depends(RequirePermission(EDIT_SITE)),
) -> SiteResponse:
    _set_image(tenant, kind, None)
    db.commit()
    db.refresh(tenant)
    return SiteResponse.model_validate(tenant)
