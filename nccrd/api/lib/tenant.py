import re
from typing import Optional

from fastapi import Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR

from nccrd.config import nccrd_config
from nccrd.db import get_db
from nccrd.db.models.rbac import Tenant


#: The site the web interface is showing, i.e. its own hostname. Sent because
#: the interface may call the API on another host (locally localhost:2022),
#: where the Host header would not tell the sites apart. Plain links, e.g. a
#: report download, can't send a header and give it as the query parameter.
SITE_HEADER = "x-nccrd-site"
SITE_PARAM = "site"
#: A province site named by its province, e.g. ?siteprovince=mpumalanga, the
#: address on any host: the page's URL carries it and the interface passes it on.
SITE_PROVINCE_HEADER = "x-nccrd-site-province"
SITE_PROVINCE_PARAM = "siteprovince"


def _tenant_of_province(db: Session, province: str):
    """The site of a province, ignoring case and punctuation (kwazulu-natal, KwaZulu Natal)."""
    letters = re.sub("[^a-z]", "", province.lower())
    if not letters:
        return None
    return db.query(Tenant).filter(func.regexp_replace(func.lower(Tenant.province), "[^a-z]", "", "g") == letters).first()


def get_current_tenant(request: Request, db: Session = Depends(get_db)) -> Tenant:
    """Resolve the active tenant from the province the request names
    (``SITE_PROVINCE_HEADER`` or ``SITE_PROVINCE_PARAM``), else the site it names
    (``SITE_HEADER`` or ``SITE_PARAM``, else its Host header): by hostname, then by the hostname's first label as
    the tenant's slug (so mccrd.environment.gov.za and mccrd.localhost are the
    same site), falling back to the tenant flagged ``is_default``."""
    province = request.headers.get(SITE_PROVINCE_HEADER) or request.query_params.get(SITE_PROVINCE_PARAM)
    tenant = _tenant_of_province(db, province) if province else None
    if tenant is not None:
        return tenant

    site = (
        request.headers.get(SITE_HEADER)
        or request.query_params.get(SITE_PARAM)
        or request.headers.get("host", "")
    )
    hostname = site.split(":")[0].strip().lower()

    tenant = db.query(Tenant).filter(Tenant.hostname == hostname).first()
    if tenant is None and "." in hostname:
        tenant = db.query(Tenant).filter(Tenant.slug == hostname.split(".")[0]).first()
    if tenant is None:
        tenant = db.query(Tenant).filter(Tenant.is_default.is_(True)).first()

    if tenant is None:
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No tenant configured for this deployment.",
        )

    return tenant


def province_segment(province: str) -> str:
    """A province site's first path segment, e.g. "KwaZulu-Natal" -> "kwazulu-natal"
    (the interface's ``provinceParam``)."""
    return re.sub(r"\s+", "-", province.strip().lower())


def _allowed_origin(request: Request) -> Optional[str]:
    """The browser's origin, if it is one the API is configured to trust (CORS)."""
    origin = (request.headers.get("origin") or "").rstrip("/")
    if not origin:
        return None
    allowed = {o.strip().rstrip("/") for o in nccrd_config.NCCRD.CORS_ORIGINS.split(",") if o.strip()}
    pattern = nccrd_config.NCCRD.CORS_ORIGIN_REGEX
    if origin in allowed or (pattern and re.fullmatch(pattern, origin)):
        return origin
    return None


def site_address(request: Request, tenant: Tenant) -> Optional[str]:
    """
    The site's address for links in emails, e.g.
    https://nccrd.environment.gov.za/mpumalanga: NCCRD_UI_URL, else the
    browser's origin if trusted, plus the province's path. Never the Host
    header, which a caller could set to send someone a link to another site.
    """
    base = (nccrd_config.NCCRD.UI_URL or "").rstrip("/") or _allowed_origin(request)
    if not base:
        return None
    return f"{base}/{province_segment(tenant.province)}" if tenant.province else base


def site_name(tenant: Tenant) -> str:
    """The short name used in emails, e.g. "MCCRD"."""
    return tenant.short_title or tenant.title or "NCCRD"
