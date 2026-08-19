from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from starlette.status import HTTP_403_FORBIDDEN

from nccrd.api.lib.auth import Authorize, Authorized
from nccrd.api.lib.tenant import get_current_tenant
from nccrd.const import NCCRDScope
from nccrd.db import get_db
from nccrd.db.models.rbac import Permission, PermissionXrefRole, Tenant, UserXrefRoleXrefTenant


def user_has_permission(db: Session, user_id: int, permission_name: str, tenant_id: int) -> bool:
    """Does ``user_id`` hold ``permission_name`` via any role assigned to them
    on ``tenant_id``?"""
    return db.query(
        db.query(UserXrefRoleXrefTenant)
        .join(PermissionXrefRole, PermissionXrefRole.role_id == UserXrefRoleXrefTenant.role_id)
        .join(Permission, Permission.id == PermissionXrefRole.permission_id)
        .filter(UserXrefRoleXrefTenant.user_id == user_id)
        .filter(UserXrefRoleXrefTenant.tenant_id == tenant_id)
        .filter(Permission.name == permission_name)
        .exists()
    ).scalar()


class RequirePermission:
    """FastAPI dependency: resolves the caller's identity (via ``Authorize``)
    and the current tenant, then checks the caller holds ``permission_name``
    on that tenant. Raises 403 if not. Returns the resolved ``Authorized``
    object on success, so it's a drop-in replacement for ``Authorize(...)``
    wherever a permission (not just an OAuth2 scope) needs to be enforced.
    """

    def __init__(self, permission_name: str):
        self.permission_name = permission_name

    def __repr__(self):
        return f'{self.__class__.__name__}(permission_name={self.permission_name!r})'

    async def __call__(
            self,
            auth: Authorized = Depends(Authorize(NCCRDScope.PROJECT_ADMIN)),
            tenant: Tenant = Depends(get_current_tenant),
            db: Session = Depends(get_db),
    ) -> Authorized:
        if not user_has_permission(db, auth.internal_user_id, self.permission_name, tenant.id):
            raise HTTPException(
                status_code=HTTP_403_FORBIDDEN,
                detail=f"Missing required permission: {self.permission_name!r}",
            )
        return auth
