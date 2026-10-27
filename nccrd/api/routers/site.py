from fastapi import APIRouter, Depends

from nccrd.api.lib.tenant import get_current_tenant
from nccrd.api.models.rbac import SiteResponse
from nccrd.db.models.rbac import Tenant

router = APIRouter()


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
