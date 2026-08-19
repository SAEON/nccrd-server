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
    """Input schema for provisioning a user (e.g. on first Hydra login)."""

    name: str = Field(..., description="Display name for the user.")
    email: str = Field(..., description="Unique email address.")
    saeon_id: Optional[str] = Field(None, description="SAEON identity provider subject, if applicable.")
    id_token: Optional[str] = Field(None, description="Raw identity token, if retained.")

    class Config:
        schema_extra = {
            "example": {
                "name": "Jane Smith",
                "email": "jane.smith@example.org",
                "saeon_id": "auth0|abc123",
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
