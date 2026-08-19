from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR

from nccrd.db import get_db
from nccrd.db.models.rbac import Tenant


def get_current_tenant(request: Request, db: Session = Depends(get_db)) -> Tenant:
    """Resolve the active tenant from the request's Host header, falling back
    to the tenant flagged ``is_default``."""
    hostname = request.headers.get("host", "").split(":")[0].lower()

    tenant = db.query(Tenant).filter(Tenant.hostname == hostname).first()
    if tenant is None:
        tenant = db.query(Tenant).filter(Tenant.is_default.is_(True)).first()

    if tenant is None:
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No tenant configured for this deployment.",
        )

    return tenant
