"""
API routers for RBAC / multi-tenancy administration: inspecting the caller's
own identity, and managing role assignments. Read endpoints are gated by the
corresponding `view-*` permission; role assignment is gated by `assign-role`.
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from nccrd.api.lib.auth import Authorize, Authorized
from nccrd.api.lib.permissions import RequirePermission
from nccrd.api.lib.tenant import get_current_tenant
from nccrd.api.models import (
    CurrentUserResponse,
    PermissionResponse,
    RoleAssignmentCreate,
    RoleResponse,
    TenantResponse,
    UserResponse,
    UserRoleTenantResponse,
)
from nccrd.const import NCCRDScope
from nccrd.db import get_db
from nccrd.db.models.rbac import (
    Permission,
    PermissionXrefRole,
    Role,
    Tenant,
    User,
    UserXrefRoleXrefTenant,
)

router = APIRouter()


@router.get(
    "/me",
    response_model=CurrentUserResponse,
    summary="Return the caller's resolved identity, current tenant, and their roles/permissions there.",
)
def get_current_user(
        db: Session = Depends(get_db),
        auth: Authorized = Depends(Authorize(NCCRDScope.PROJECT_ADMIN)),
        tenant: Tenant = Depends(get_current_tenant),
) -> CurrentUserResponse:
    user = db.query(User).filter(User.id == auth.internal_user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Resolved user not found.")

    assignments = (
        db.query(UserXrefRoleXrefTenant)
        .filter(UserXrefRoleXrefTenant.user_id == user.id)
        .filter(UserXrefRoleXrefTenant.tenant_id == tenant.id)
        .all()
    )
    role_ids = [a.role_id for a in assignments]
    roles = db.query(Role).filter(Role.id.in_(role_ids)).all() if role_ids else []

    permissions: List[str] = []
    if role_ids:
        permissions = [
            name for (name,) in (
                db.query(Permission.name)
                .join(PermissionXrefRole, PermissionXrefRole.permission_id == Permission.id)
                .filter(PermissionXrefRole.role_id.in_(role_ids))
                .distinct()
                .all()
            )
        ]

    return CurrentUserResponse(
        user=UserResponse.from_orm(user),
        tenant=TenantResponse.from_orm(tenant),
        roles=[r.name for r in roles],
        permissions=permissions,
    )


@router.get(
    "/users",
    response_model=List[UserResponse],
    summary="List users.",
)
def list_users(
        db: Session = Depends(get_db),
        auth: Authorized = Depends(RequirePermission("view-users")),
) -> List[User]:
    return db.query(User).filter(User.deleted.isnot(True)).all()


@router.get(
    "/roles",
    response_model=List[RoleResponse],
    summary="List roles.",
)
def list_roles(
        db: Session = Depends(get_db),
        auth: Authorized = Depends(RequirePermission("view-roles")),
) -> List[Role]:
    return db.query(Role).all()


@router.get(
    "/permissions",
    response_model=List[PermissionResponse],
    summary="List permissions.",
)
def list_permissions(
        db: Session = Depends(get_db),
        auth: Authorized = Depends(RequirePermission("view-permissions")),
) -> List[Permission]:
    return db.query(Permission).all()


@router.get(
    "/tenants",
    response_model=List[TenantResponse],
    summary="List tenants.",
)
def list_tenants(
        db: Session = Depends(get_db),
        auth: Authorized = Depends(RequirePermission("view-tenants")),
) -> List[Tenant]:
    return db.query(Tenant).all()


@router.post(
    "/users/{user_id}/roles",
    response_model=UserRoleTenantResponse,
    summary="Grant a user a role on a tenant.",
)
def assign_role(
        user_id: int,
        assignment: RoleAssignmentCreate,
        db: Session = Depends(get_db),
        auth: Authorized = Depends(RequirePermission("assign-role")),
) -> UserXrefRoleXrefTenant:
    if not db.query(User).filter(User.id == user_id).first():
        raise HTTPException(status_code=404, detail="User not found.")
    if not db.query(Role).filter(Role.id == assignment.role_id).first():
        raise HTTPException(status_code=404, detail="Role not found.")
    if not db.query(Tenant).filter(Tenant.id == assignment.tenant_id).first():
        raise HTTPException(status_code=404, detail="Tenant not found.")

    existing = (
        db.query(UserXrefRoleXrefTenant)
        .filter(UserXrefRoleXrefTenant.user_id == user_id)
        .filter(UserXrefRoleXrefTenant.role_id == assignment.role_id)
        .filter(UserXrefRoleXrefTenant.tenant_id == assignment.tenant_id)
        .first()
    )
    if existing:
        return existing

    link = UserXrefRoleXrefTenant(
        user_id=user_id,
        role_id=assignment.role_id,
        tenant_id=assignment.tenant_id,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


@router.delete(
    "/users/{user_id}/roles/{assignment_id}",
    summary="Revoke a user's role assignment.",
)
def revoke_role(
        user_id: int,
        assignment_id: int,
        db: Session = Depends(get_db),
        auth: Authorized = Depends(RequirePermission("assign-role")),
) -> dict:
    link = (
        db.query(UserXrefRoleXrefTenant)
        .filter(UserXrefRoleXrefTenant.id == assignment_id)
        .filter(UserXrefRoleXrefTenant.user_id == user_id)
        .first()
    )
    if not link:
        raise HTTPException(status_code=404, detail="Role assignment not found.")

    db.delete(link)
    db.commit()
    return {"detail": "Role assignment revoked."}
