from typing import List, Set

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from starlette.status import HTTP_403_FORBIDDEN

from nccrd.api.lib.auth import Authorize, Authorized
from nccrd.api.lib.tenant import get_current_tenant
from nccrd.db import get_db
from nccrd.db.models.rbac import Permission, PermissionXrefRole, Role, Tenant, User, UserXrefRoleXrefTenant


def _default_tenant_id(db: Session):
    return db.query(Tenant.id).filter(Tenant.is_default.is_(True)).scalar()


def _role_tenant_ids(db: Session, tenant_id: int) -> set:
    """The sites whose roles apply on ``tenant_id``: itself and the national
    (default) site, whose roles apply on every site."""
    return {tenant_id, _default_tenant_id(db)} - {None}


def user_has_permission(db: Session, user_id: int, permission_name: str, tenant_id: int) -> bool:
    """Does ``user_id`` hold ``permission_name`` via any role assigned to them
    on ``tenant_id``, or on the national site?"""
    return db.query(
        db.query(UserXrefRoleXrefTenant)
        .join(PermissionXrefRole, PermissionXrefRole.role_id == UserXrefRoleXrefTenant.role_id)
        .join(Permission, Permission.id == PermissionXrefRole.permission_id)
        .filter(UserXrefRoleXrefTenant.user_id == user_id)
        .filter(UserXrefRoleXrefTenant.tenant_id.in_(_role_tenant_ids(db, tenant_id)))
        .filter(Permission.name == permission_name)
        .exists()
    ).scalar()


def user_role_assignments(db: Session, user_id: int, tenant_id: int) -> List[UserXrefRoleXrefTenant]:
    """The user's role assignments that apply on ``tenant_id`` (see ``user_has_permission``)."""
    return (
        db.query(UserXrefRoleXrefTenant)
        .filter(UserXrefRoleXrefTenant.user_id == user_id)
        .filter(UserXrefRoleXrefTenant.tenant_id.in_(_role_tenant_ids(db, tenant_id)))
        .all()
    )


def user_permissions(db: Session, user_id: int, tenant_id: int) -> Set[str]:
    role_ids = {a.role_id for a in user_role_assignments(db, user_id, tenant_id)}
    return role_permissions(db, role_ids)


def role_permissions(db: Session, role_ids) -> Set[str]:
    if not role_ids:
        return set()
    return {
        name for (name,) in (
            db.query(Permission.name)
            .join(PermissionXrefRole, PermissionXrefRole.permission_id == Permission.id)
            .filter(PermissionXrefRole.role_id.in_(role_ids))
        )
    }


def people_with_permission(db: Session, permission_name: str, tenant: Tenant, fall_back: bool = True) -> List[User]:
    """
    Who to tell about the site's work, e.g. its reviewers: the people with
    the permission through a role on ``tenant`` itself, else (if it has none)
    those with it on the national site (unless ``fall_back`` is False).
    """
    def holders(tenant_id):
        return (
            db.query(User)
            .join(UserXrefRoleXrefTenant, UserXrefRoleXrefTenant.user_id == User.id)
            .join(PermissionXrefRole, PermissionXrefRole.role_id == UserXrefRoleXrefTenant.role_id)
            .join(Permission, Permission.id == PermissionXrefRole.permission_id)
            .filter(UserXrefRoleXrefTenant.tenant_id == tenant_id, Permission.name == permission_name)
            .filter(User.deleted.isnot(True))
            .filter((User.registration_status.is_(None)) | (User.registration_status == "approved"))
            .distinct()
            .all()
        )

    people = holders(tenant.id)
    default_id = _default_tenant_id(db)
    if fall_back and not people and default_id is not None and default_id != tenant.id:
        people = holders(default_id)
    return people


# ── Who may grant what ────────────────────────────────────────────────────────


def manageable_tenants(db: Session, user_id: int, current: Tenant) -> List[Tenant]:
    """
    The sites on which the user may manage roles: every site for an admin of
    the national site, else the current site if they're its admin.
    """
    default_id = _default_tenant_id(db)
    national_admin = default_id is not None and db.query(
        db.query(UserXrefRoleXrefTenant)
        .join(PermissionXrefRole, PermissionXrefRole.role_id == UserXrefRoleXrefTenant.role_id)
        .join(Permission, Permission.id == PermissionXrefRole.permission_id)
        .filter(UserXrefRoleXrefTenant.user_id == user_id)
        .filter(UserXrefRoleXrefTenant.tenant_id == default_id)
        .filter(Permission.name == "assign-role")
        .exists()
    ).scalar()
    if national_admin:
        return db.query(Tenant).order_by(Tenant.is_default.desc(), Tenant.title).all()
    return [current] if user_has_permission(db, user_id, "assign-role", current.id) else []


def grantable_roles(db: Session, user_id: int, tenant: Tenant) -> List[Role]:
    """Roles the user may grant on ``tenant``: those whose permissions they
    hold there themselves, so nobody can give out more than they have."""
    own = user_permissions(db, user_id, tenant.id)
    return [
        role for role in db.query(Role).order_by(Role.name).all()
        if role_permissions(db, {role.id}) <= own
    ]


def require_grant(db: Session, user_id: int, current: Tenant, role_id: int, tenant_id: int) -> None:
    """Raise 403 unless the user may grant (or take away) ``role_id`` on ``tenant_id``."""
    tenant = next((t for t in manageable_tenants(db, user_id, current) if t.id == tenant_id), None)
    if tenant is None:
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="You can't manage roles on that site.")
    if role_id not in {r.id for r in grantable_roles(db, user_id, tenant)}:
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="You can only give roles whose permissions you have yourself.")


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
            auth: Authorized = Depends(Authorize()),
            tenant: Tenant = Depends(get_current_tenant),
            db: Session = Depends(get_db),
    ) -> Authorized:
        if not user_has_permission(db, auth.internal_user_id, self.permission_name, tenant.id):
            raise HTTPException(
                status_code=HTTP_403_FORBIDDEN,
                detail=f"Missing required permission: {self.permission_name!r}",
            )
        return auth
