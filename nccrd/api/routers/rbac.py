"""
API routers for RBAC / multi-tenancy administration: inspecting the caller's
own identity, and managing role assignments. Read endpoints are gated by the
corresponding `view-*` permission; role assignment is gated by `assign-role`.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from starlette.requests import Request

from nccrd.api.lib.auth import Authorize, Authorized, generate_temp_password, hash_password
from nccrd.api.lib.permissions import (
    RequirePermission,
    grantable_roles,
    manageable_tenants,
    require_grant,
    role_permissions,
    user_role_assignments,
)
from nccrd.api.lib import notify
from nccrd.api.lib.tenant import get_current_tenant, site_address
from nccrd.api.models import (
    CurrentUserResponse,
    PermissionResponse,
    RoleAssignmentCreate,
    RoleResponse,
    TenantResponse,
    UserCreate,
    UserCreateResponse,
    UserResponse,
    UserRoleTenantResponse,
    RegistrationApproval,
    RegistrationResponse,
    GrantOptions,
    SiteOption,
    UserRoleDetail,
    UserWithRoles,
)
from nccrd.db import get_db
from nccrd.db.models.rbac import (
    Login,
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
        auth: Authorized = Depends(Authorize()),
        tenant: Tenant = Depends(get_current_tenant),
) -> CurrentUserResponse:
    user = db.query(User).filter(User.id == auth.internal_user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Resolved user not found.")

    # Roles on the national site count on every site (see user_has_permission).
    role_ids = {a.role_id for a in user_role_assignments(db, user.id, tenant.id)}
    roles = db.query(Role).filter(Role.id.in_(role_ids)).order_by(Role.name).all() if role_ids else []
    permissions = sorted(role_permissions(db, role_ids))

    return CurrentUserResponse(
        user=UserResponse.model_validate(user),
        tenant=TenantResponse.model_validate(tenant),
        roles=[r.name for r in roles],
        permissions=permissions,
    )


def _site_name(tenant: Tenant) -> str:
    return tenant.short_title or tenant.title or tenant.hostname


@router.get(
    "/users",
    response_model=List[UserWithRoles],
    summary="People with accounts, and their roles on the sites the caller manages.",
)
def list_users(
        q: Optional[str] = None,
        db: Session = Depends(get_db),
        tenant: Tenant = Depends(get_current_tenant),
        auth: Authorized = Depends(RequirePermission("assign-role")),
) -> List[UserWithRoles]:
    """
    An admin of the national site sees everyone; a province site's admin sees
    the people with a role on their site, plus anyone whose full email
    address they search for, so they can give that person a role.
    ``q`` matches part of a name or email address. At most 500 are listed.
    """
    sites = {t.id: t for t in manageable_tenants(db, auth.internal_user_id, tenant)}
    national = any(t.is_default for t in sites.values())
    term = (q or "").strip().lower()

    query = db.query(User).filter(
        User.deleted.isnot(True),
        or_(User.registration_status.is_(None), User.registration_status == "approved"),
    )
    if term:
        query = query.filter(or_(func.lower(User.name).contains(term), func.lower(User.email).contains(term)))
    if not national:
        with_role_here = db.query(UserXrefRoleXrefTenant.user_id).filter(UserXrefRoleXrefTenant.tenant_id.in_(sites))
        query = query.filter(or_(User.id.in_(with_role_here), func.lower(User.email) == term))
    users = query.order_by(func.lower(User.name)).limit(500).all()

    ids = [u.id for u in users]
    last_login = dict(
        db.query(Login.user_id, func.max(Login.timestamp)).filter(Login.user_id.in_(ids)).group_by(Login.user_id)
    ) if ids else {}
    role_names = {r.id: r.name for r in db.query(Role)}
    assignments = (
        db.query(UserXrefRoleXrefTenant)
        .filter(UserXrefRoleXrefTenant.user_id.in_(ids), UserXrefRoleXrefTenant.tenant_id.in_(sites))
        .order_by(UserXrefRoleXrefTenant.id)
        .all()
    ) if ids else []
    roles_of = {}
    for a in assignments:
        roles_of.setdefault(a.user_id, []).append(UserRoleDetail(
            id=a.id, role_id=a.role_id, role=role_names[a.role_id], tenant_id=a.tenant_id, site=_site_name(sites[a.tenant_id]),
        ))
    return [
        UserWithRoles(
            id=u.id, name=u.name, email=u.email, organisation=u.organisation, created_at=u.created_at,
            last_login=last_login.get(u.id), roles=roles_of.get(u.id, []),
        )
        for u in users
    ]


@router.get(
    "/grants",
    response_model=GrantOptions,
    summary="The sites on which the caller manages roles, and the roles they may grant.",
)
def list_grants(
        db: Session = Depends(get_db),
        tenant: Tenant = Depends(get_current_tenant),
        auth: Authorized = Depends(RequirePermission("assign-role")),
) -> GrantOptions:
    sites = manageable_tenants(db, auth.internal_user_id, tenant)
    return GrantOptions(
        sites=[SiteOption(id=t.id, name=_site_name(t), is_default=t.is_default) for t in sites],
        roles=[RoleResponse.model_validate(r) for r in grantable_roles(db, auth.internal_user_id, tenant)],
    )


@router.post(
    "/users",
    response_model=UserCreateResponse,
    summary="Provision a new user with a one-time temporary password, optionally granting a role on a "
            "tenant in the same call. Gated behind `assign-role` since creating accounts is an admin-tier action.",
)
def create_user(
        body: UserCreate,
        db: Session = Depends(get_db),
        current: Tenant = Depends(get_current_tenant),
        auth: Authorized = Depends(RequirePermission("assign-role")),
) -> UserCreateResponse:
    if db.query(User).filter(func.lower(User.email) == body.email.strip().lower()).first():
        raise HTTPException(status_code=409, detail="A user with this email already exists.")

    if (body.role_id is None) != (body.tenant_id is None):
        raise HTTPException(status_code=422, detail="role_id and tenant_id must be given together.")

    role, tenant = None, None
    if body.role_id is not None:
        role = db.query(Role).filter(Role.id == body.role_id).first()
        if not role:
            raise HTTPException(status_code=404, detail="Role not found.")
        tenant = db.query(Tenant).filter(Tenant.id == body.tenant_id).first()
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found.")
        require_grant(db, auth.internal_user_id, current, role.id, tenant.id)

    temp_password = generate_temp_password()
    user = User(
        name=body.name,
        email=body.email,
        password_hash=hash_password(temp_password),
        password_set_at=None,  # must change on first login
    )
    db.add(user)
    db.flush()  # assign user.id without committing, so the role link below is part of the same transaction

    link = None
    if role is not None:
        link = UserXrefRoleXrefTenant(user_id=user.id, role_id=role.id, tenant_id=tenant.id)
        db.add(link)

    db.commit()
    db.refresh(user)
    if link is not None:
        db.refresh(link)

    return UserCreateResponse(
        user=UserResponse.model_validate(user),
        temp_password=temp_password,
        role_assignment=UserRoleTenantResponse.model_validate(link) if link is not None else None,
    )


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
        current: Tenant = Depends(get_current_tenant),
        auth: Authorized = Depends(RequirePermission("assign-role")),
) -> UserXrefRoleXrefTenant:
    user = db.query(User).filter(User.id == user_id, User.deleted.isnot(True)).first()
    if not user or user.registration_status in ("pending", "rejected"):
        raise HTTPException(status_code=404, detail="User not found.")
    if not db.query(Role).filter(Role.id == assignment.role_id).first():
        raise HTTPException(status_code=404, detail="Role not found.")
    if not db.query(Tenant).filter(Tenant.id == assignment.tenant_id).first():
        raise HTTPException(status_code=404, detail="Tenant not found.")
    require_grant(db, auth.internal_user_id, current, assignment.role_id, assignment.tenant_id)

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
        current: Tenant = Depends(get_current_tenant),
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
    if user_id == auth.internal_user_id:
        # So nobody locks themselves out; another admin can do it.
        raise HTTPException(status_code=403, detail="You can't take away your own roles.")
    require_grant(db, auth.internal_user_id, current, link.role_id, link.tenant_id)

    db.delete(link)
    db.commit()
    return {"detail": "Role assignment revoked."}


# ──────────────────────────────────────────────────────────────────────────────
# Self sign-up review (POST /auth/register creates the requests)
# ──────────────────────────────────────────────────────────────────────────────


def _registrations_on(db: Session, auth: Authorized, tenant: Tenant):
    """Requests made on the sites the caller manages; those with no site
    (made before sites were recorded) count as the national site's."""
    sites = manageable_tenants(db, auth.internal_user_id, tenant)
    ids = [t.id for t in sites]
    on_site = User.registration_tenant_id.in_(ids)
    if any(t.is_default for t in sites):
        on_site = or_(on_site, User.registration_tenant_id.is_(None))
    return db.query(User).filter(on_site, User.deleted.isnot(True))


@router.get(
    "/registrations",
    response_model=List[RegistrationResponse],
    summary="Account requests awaiting review (or with another status), newest first.",
)
def list_registrations(
        status: Literal["pending", "approved", "rejected"] = "pending",
        db: Session = Depends(get_db),
        tenant: Tenant = Depends(get_current_tenant),
        auth: Authorized = Depends(RequirePermission("assign-role")),
) -> List[User]:
    return (
        _registrations_on(db, auth, tenant)
        .filter(User.registration_status == status)
        .order_by(User.created_at.desc())
        .all()
    )


def _pending_registration(db: Session, auth: Authorized, tenant: Tenant, user_id: int) -> User:
    user = _registrations_on(db, auth, tenant).filter(User.id == user_id).first()
    if user is None or user.registration_status != "pending":
        raise HTTPException(status_code=404, detail="No pending account request with that id.")
    return user


@router.post(
    "/registrations/{user_id}/approve",
    response_model=RegistrationResponse,
    summary="Approve an account request, granting a role on the current tenant.",
)
def approve_registration(
        user_id: int,
        body: RegistrationApproval,
        request: Request,
        background: BackgroundTasks,
        db: Session = Depends(get_db),
        tenant: Tenant = Depends(get_current_tenant),
        auth: Authorized = Depends(RequirePermission("assign-role")),
) -> User:
    user = _pending_registration(db, auth, tenant, user_id)
    if not db.query(Role).filter(Role.id == body.role_id).first():
        raise HTTPException(status_code=404, detail="Role not found.")
    require_grant(db, auth.internal_user_id, tenant, body.role_id, tenant.id)
    db.add(UserXrefRoleXrefTenant(user_id=user.id, role_id=body.role_id, tenant_id=tenant.id))
    user.registration_status = "approved"
    db.commit()
    db.refresh(user)
    notify.registration_approved(background, user, tenant, site_address(request, tenant))
    return user


@router.post(
    "/registrations/{user_id}/reject",
    response_model=RegistrationResponse,
    summary="Reject an account request; the account can't log in.",
)
def reject_registration(
        user_id: int,
        background: BackgroundTasks,
        db: Session = Depends(get_db),
        tenant: Tenant = Depends(get_current_tenant),
        auth: Authorized = Depends(RequirePermission("assign-role")),
) -> User:
    user = _pending_registration(db, auth, tenant, user_id)
    user.registration_status = "rejected"
    db.commit()
    db.refresh(user)
    notify.registration_rejected(background, user, tenant)
    return user
