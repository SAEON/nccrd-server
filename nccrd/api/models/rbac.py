"""
Pydantic v1 schemas for multi-tenant RBAC (User, Role, Permission, Tenant).
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import ConfigDict, BaseModel, Field


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
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "name": "Jane Smith",
            "email": "jane.smith@example.org",
            "role_id": 8,
            "tenant_id": 6,
        }
    })


class UserResponse(BaseModel):
    id: int
    uuid: UUID
    name: str
    email: str
    saeon_id: Optional[str] = None
    created_at: datetime
    deleted: bool
    model_config = ConfigDict(from_attributes=True)


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
    model_config = ConfigDict(from_attributes=True)


class PermissionResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


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
    model_config = ConfigDict(from_attributes=True)


class SiteResponse(BaseModel):
    """What the web interface needs to show the current site: its names, the
    province it covers, and its branding. Public: no IDs, roles or settings."""
    hostname: str
    title: Optional[str] = None
    short_title: Optional[str] = None
    province: Optional[str] = None
    logo_url: Optional[str] = None
    flag_url: Optional[str] = None
    contact_email: Optional[str] = None
    theme: Optional[dict] = None
    front_matter: Optional[dict] = None
    hero_image: Optional[dict] = None
    is_default: bool
    model_config = ConfigDict(from_attributes=True)


#: The About page's sections, in the order it shows them.
SITE_SECTIONS = ("about", "context", "explore", "submit")


class SiteSection(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field("", max_length=6000, description="Plain text; a blank line starts a new paragraph.")


class HeroCredit(BaseModel):
    """Who took the front-page photo, and its licence, shown on the photo."""
    credit: Optional[str] = Field(None, max_length=200)
    license: Optional[str] = Field(None, max_length=100)
    source_url: Optional[str] = Field(None, max_length=500, pattern=r"^https?://")
    license_url: Optional[str] = Field(None, max_length=500, pattern=r"^https?://")


class SiteUpdate(BaseModel):
    """What a site's admin can change (permission edit-site). Left out = unchanged."""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    short_title: Optional[str] = Field(None, min_length=1, max_length=20)
    contact_email: Optional[str] = Field(None, max_length=200, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    colour: Optional[str] = Field(None, pattern=r"^#[0-9a-fA-F]{6}$", description="The main colour, e.g. #622700.")
    sections: Optional[Dict[str, SiteSection]] = Field(None, description=f"About sections by key: {', '.join(SITE_SECTIONS)}.")
    hero_credit: Optional[HeroCredit] = None


class UserRoleTenantResponse(BaseModel):
    """A single user-role-tenant assignment, as used for permission checks."""

    id: int
    user_id: int
    role_id: int
    tenant_id: int
    model_config = ConfigDict(from_attributes=True)


class RoleAssignmentCreate(BaseModel):
    """Input schema for granting a user a role on a tenant."""

    role_id: int = Field(..., description="nccrd.role.id to grant.")
    tenant_id: int = Field(..., description="nccrd.tenant.id the role applies to.")
    model_config = ConfigDict(json_schema_extra={"example": {"role_id": 8, "tenant_id": 6}})


class CurrentUserResponse(BaseModel):
    """Response for GET /rbac/me — the resolved caller, current tenant, and
    the roles/permissions that apply there."""

    user: UserResponse
    tenant: TenantResponse
    roles: List[str]
    permissions: List[str]


UserCreateResponse.model_rebuild()


class UserRoleDetail(BaseModel):
    """One of a person's roles, on one site, for the user management page."""

    id: int = Field(..., description="The assignment's id, to take the role away.")
    role_id: int
    role: str
    tenant_id: int
    site: str = Field(..., description="The site's short name, e.g. MCCRD.")


class UserWithRoles(BaseModel):
    """A person on the user management page, with the roles the caller can see."""

    id: int
    name: str
    email: str
    organisation: Optional[str] = None
    created_at: datetime
    last_login: Optional[datetime] = None
    roles: List[UserRoleDetail]


class SiteOption(BaseModel):
    id: int
    name: str
    is_default: bool


class GrantOptions(BaseModel):
    """What the caller may hand out: the sites they manage and the roles they may grant."""

    sites: List[SiteOption]
    roles: List[RoleResponse]


class RegistrationResponse(BaseModel):
    """A self sign-up request, for the admin's review queue."""

    id: int
    name: str
    email: str
    organisation: Optional[str] = None
    registration_note: Optional[str] = None
    registration_status: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class RegistrationApproval(BaseModel):
    """Role to grant (on the current tenant) when approving a sign-up."""

    role_id: int
