"""
SQLAlchemy ORM models for multi-tenant RBAC.

Mirrors the tables created by alembic migration 0002
(schema_hardening_and_multi_tenant_rbac). These models let application code
(auth resolution, permission checks, tenant scoping) query and join against
users, roles, permissions, and tenants instead of relying on raw integer
columns with no FK target.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from nccrd.db import Base


class User(Base):
    __tablename__ = "user"
    __table_args__ = {"schema": "nccrd"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4)
    name = Column(String(500), nullable=False)
    email = Column(String(500), unique=True, nullable=False)
    saeon_id = Column(String(255))
    id_token = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    deleted = Column(Boolean, default=False, nullable=False)

    role_assignments = relationship(
        "UserXrefRoleXrefTenant",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class Role(Base):
    __tablename__ = "role"
    __table_args__ = {"schema": "nccrd"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=False)
    description = Column(Text)

    permission_links = relationship(
        "PermissionXrefRole",
        back_populates="role",
        cascade="all, delete-orphan",
    )


class Permission(Base):
    __tablename__ = "permission"
    __table_args__ = {"schema": "nccrd"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=False)
    description = Column(Text)


class PermissionXrefRole(Base):
    __tablename__ = "permission_xref_role"
    __table_args__ = {"schema": "nccrd"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    permission_id = Column(Integer, ForeignKey("nccrd.permission.id"), nullable=False)
    role_id = Column(Integer, ForeignKey("nccrd.role.id"), nullable=False)

    role = relationship("Role", back_populates="permission_links")
    permission = relationship("Permission")


class Tenant(Base):
    __tablename__ = "tenant"
    __table_args__ = {"schema": "nccrd"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    hostname = Column(String(500), unique=True, nullable=False)
    title = Column(String(500))
    theme = Column(JSON)
    contact_email = Column(String(500))
    is_default = Column(Boolean, default=False, nullable=False)
    include_unbounded_submissions = Column(Boolean, default=False, nullable=False)


class TenantXrefSubmission(Base):
    __tablename__ = "tenant_xref_submission"
    __table_args__ = {"schema": "nccrd"}

    tenant_id = Column(Integer, ForeignKey("nccrd.tenant.id"), primary_key=True)
    submission_id = Column(
        UUID(as_uuid=True), ForeignKey("nccrd.submission.id"), primary_key=True
    )


class UserXrefRoleXrefTenant(Base):
    __tablename__ = "user_xref_role_xref_tenant"
    __table_args__ = {"schema": "nccrd"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("nccrd.user.id"), nullable=False)
    role_id = Column(Integer, ForeignKey("nccrd.role.id"), nullable=False)
    tenant_id = Column(Integer, ForeignKey("nccrd.tenant.id"), nullable=False)

    user = relationship("User", back_populates="role_assignments")
    role = relationship("Role")
    tenant = relationship("Tenant")
