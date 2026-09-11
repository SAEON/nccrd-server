"""
Pydantic v1 schemas for multi-tenant RBAC (User, Role, Permission, Tenant).
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────────────────────────────────────
# User
# ──────────────────────────────────────────────────────────────────────────────


class UserCreate(BaseModel):
    """Input schema for an admin provisioning a new user. A random temporary
    password is generated server-side and returned once in the response —
    it is not retrievable afterwards. The new user must change it on their
    first login.

    ``role_id`` and ``tenant_id`` are optional and must be given together —
    when present, the new user is granted that role on that tenant in the
    same request, instead of a separate ``POST /users/{id}/roles`` call."""

    name: str = Field(..., description="Display name for the user.")
    email: str = Field(..., description="Unique email address.")
    role_id: Optional[int] = Field(None, description="nccrd.role.id to grant immediately. Requires tenant_id.")
    tenant_id: Optional[int] = Field(None, description="nccrd.tenant.id the role applies to. Requires role_id.")

    class Config:
        schema_extra = {
            "example": {
                "name": "Jane Smith",
                "email": "jane.smith@example.org",
                "role_id": 8,
                "tenant_id": 6,
            }
        }


class UserResponse(BaseModel):
    id: int
    uuid: UUID
    name: str
    email: str
    saeon_id: Optional[str] = None
    created_at: datetime
    deleted: bool

    class Config:
        orm_mode = True


class UserCreateResponse(BaseModel):
    """Response for POST /rbac/users — the new user plus their one-time
    temporary password, to be relayed to them out-of-band. ``role_assignment``
    is set only if ``role_id``/``tenant_id`` were given in the request."""

    user: UserResponse
    temp_password: str = Field(..., description="One-time temporary password. Not retrievable after this response.")
    role_assignment: Optional["UserRoleTenantResponse"] = None


# ──────────────────────────────────────────────────────────────────────────────
# Role / Permission
# ──────────────────────────────────────────────────────────────────────────────


class RoleResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None

    class Config:
        orm_mode = True


class PermissionResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None

    class Config:
        orm_mode = True


# ──────────────────────────────────────────────────────────────────────────────
# Tenant
# ──────────────────────────────────────────────────────────────────────────────


class TenantResponse(BaseModel):
    id: int
    hostname: str
    title: Optional[str] = None
    contact_email: Optional[str] = None
    is_default: bool
    include_unbounded_submissions: bool

    class Config:
        orm_mode = True


class UserRoleTenantResponse(BaseModel):
    """A single user-role-tenant assignment, as used for permission checks."""

    id: int
    user_id: int
    role_id: int
    tenant_id: int

    class Config:
        orm_mode = True


class RoleAssignmentCreate(BaseModel):
    """Input schema for granting a user a role on a tenant."""

    role_id: int = Field(..., description="nccrd.role.id to grant.")
    tenant_id: int = Field(..., description="nccrd.tenant.id the role applies to.")

    class Config:
        schema_extra = {"example": {"role_id": 8, "tenant_id": 6}}


class CurrentUserResponse(BaseModel):
    """Response for GET /rbac/me — the resolved caller, current tenant, and
    the roles/permissions that apply there."""

    user: UserResponse
    tenant: TenantResponse
    roles: List[str]
    permissions: List[str]


UserCreateResponse.update_forward_refs()
