from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR

from nccrd.db import get_db
from nccrd.db.models.rbac import Tenant


#: The site the web interface is showing, i.e. its own hostname. Sent because
#: the interface may call the API on another host (locally localhost:2022),
#: where the Host header would not tell the sites apart. Plain links, e.g. a
#: report download, can't send a header and give it as the query parameter.
SITE_HEADER = "x-nccrd-site"
SITE_PARAM = "site"


def get_current_tenant(request: Request, db: Session = Depends(get_db)) -> Tenant:
    """Resolve the active tenant from the site the request names (``SITE_HEADER``
    or ``SITE_PARAM``, else its Host header): by hostname, then by the hostname's first label as
    the tenant's slug (so mccrd.environment.gov.za and mccrd.localhost are the
    same site), falling back to the tenant flagged ``is_default``."""
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
