"""
SQLAlchemy ORM models for NCCRD submissions.

Changelog vs. previous version
--------------------------------
* ``Adaptaion``  →  ``Adaptation``  (class + table name corrected).
* ``Mitigation.enviromental_co_benefit``  →  ``environmental_co_benefit``.
* ``Submission.platfrom``  →  ``platform``.
* Removed ``project_manager_position``; merged ``project_manager_phone`` /
  ``project_manager_mobile`` into ``project_manager_contact_number``.
* ``intervention_measurement``, ``implementation_status``, and ``funding_type``
  are now strict SQLAlchemy Enum columns (stored as VARCHAR + CHECK constraint
  via ``native_enum=False`` for safe Alembic migrations).
* New ``ProgressReport`` model with a one-to-many relationship to ``Submission``
  to support MRV / progress-report document tracking.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from nccrd.db import Base


# ──────────────────────────────────────────────────────────────────────────────
# Python Enums (single source of truth shared with Pydantic schemas)
# ──────────────────────────────────────────────────────────────────────────────


class InterventionMeasurement(str, enum.Enum):
    """Allowed values for the primary intervention type."""

    MITIGATION = "Mitigation"
    ADAPTATION = "Adaptation"
    CROSS_CUTTING = "Cross Cutting"


class ImplementationStatus(str, enum.Enum):
    """Lifecycle / implementation status options."""

    PLANNED = "Planned"
    UNDER_IMPLEMENTATION = "Under Implementation"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"
    ON_HOLD = "On Hold"


class FundingType(str, enum.Enum):
    """Recognised funding mechanism categories."""

    GRANT = "Grant"
    LOAN = "Loan"
    OWN_FUNDING = "Own Funding"
    PUBLIC_PRIVATE = "Public-Private Partnership"
    NONE = "None"
    OTHER = "Other"


# ──────────────────────────────────────────────────────────────────────────────
# Submission (primary entity)
# ──────────────────────────────────────────────────────────────────────────────


class Submission(Base):
    """
    Primary submission record representing a climate-change project or
    intervention.  Child records (Adaptation, Mitigation, ProgressReport) link
    back to this via ``submission.id`` (UUID).
    """

    __tablename__ = "submission"
    __table_args__ = {"schema": "nccrd"}

    # Surrogate integer key for internal joins; UUID is the public identifier.
    _id = Column(Integer, primary_key=True, autoincrement=True)
    id = Column(UUID(as_uuid=True), unique=True, default=uuid.uuid4, nullable=False)

    # ── Project overview ──────────────────────────────────────────────────────
    title = Column(String, nullable=False)
    intervention_measurement = Column(
        SAEnum(
            *[e.value for e in InterventionMeasurement],
            name="intervention_measurement_enum",
            native_enum=False,   # Stored as VARCHAR + CHECK; no PG ENUM type needed.
        ),
        nullable=False,
    )
    description = Column(Text)
    implementation_status = Column(
        SAEnum(
            *[e.value for e in ImplementationStatus],
            name="implementation_status_enum",
            native_enum=False,
        )
    )
    implementation_organization = Column(String)
    implementation_partners_other = Column(String)
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    link = Column(String)

    # ── Funding ───────────────────────────────────────────────────────────────
    funding_organization = Column(String)
    funding_type = Column(
        SAEnum(
            *[e.value for e in FundingType],
            name="funding_type_enum",
            native_enum=False,
        )
    )
    funding_amount = Column(Float)
    estimated_budget_cost = Column(String)

    # ── Geographic location (GeoJSON-compatible JSONB) ────────────────────────
    geo_location = Column(JSONB)

    # ── Project manager contact ───────────────────────────────────────────────
    project_manager_name = Column(String)
    project_manager_organization = Column(String)
    project_manager_email = Column(String)
    # Consolidated from project_manager_phone + project_manager_mobile.
    project_manager_contact_number = Column(String)

    # ── Submission workflow ───────────────────────────────────────────────────
    submission_status = Column(String)
    submission_status_updated_by = Column(
        Integer, ForeignKey("nccrd.user.id"), nullable=True
    )
    submission_comments = Column(String)
    issubmitted = Column(Boolean, default=False)

    # ── Research flag ─────────────────────────────────────────────────────────
    research = Column(String)

    # ── Metadata ──────────────────────────────────────────────────────────────
    platform = Column(String)          # Fixed typo: was ``platfrom``.
    data_source = Column(String)       # Provenance: 'sqlserver_legacy' | 'react_app' | 'bulk_upload' | free-form label
    createdby = Column(Integer, ForeignKey("nccrd.user.id"))
    createdate = Column(DateTime)
    updatedate = Column(DateTime)
    updatedby = Column(Integer, ForeignKey("nccrd.user.id"))
    deletedby = Column(Integer, ForeignKey("nccrd.user.id"))
    deletedate = Column(DateTime)
    deleted = Column(Boolean, default=False)

    # ── Relationships ─────────────────────────────────────────────────────────
    # Note: bare List[] annotations break SQLAlchemy 2.x declarative scanning;
    # omit the type hint here and rely on Column() / relationship() definitions.
    progress_reports = relationship(
        "ProgressReport",
        back_populates="submission",
        cascade="all, delete-orphan",
        lazy="select",
    )
    adaptations = relationship(
        "Adaptation",
        back_populates="submission",
        cascade="all, delete-orphan",
        lazy="select",
    )
    mitigations = relationship(
        "Mitigation",
        back_populates="submission",
        cascade="all, delete-orphan",
        lazy="select",
    )


# ──────────────────────────────────────────────────────────────────────────────
# Adaptation (child of Submission)
# ──────────────────────────────────────────────────────────────────────────────


class Adaptation(Base):
    """
    Adaptation-specific details for a submission.  Renamed from the
    previous ``Adaptaion`` (typo corrected in both class and table name).
    """

    __tablename__ = "adaptation"     # Was ``adaptaion``; corrected.
    __table_args__ = {"schema": "nccrd"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    submission_id = Column(
        UUID(as_uuid=True),
        ForeignKey("nccrd.submission.id"),
        nullable=False,
    )

    # ── Adaptation details ────────────────────────────────────────────────────
    sector = Column(String)
    national_policy = Column(String)
    intervention_goal = Column(String)
    provincial_municipal = Column(String)
    hazard = Column(String)

    # ── Progress ──────────────────────────────────────────────────────────────
    progress_calculator = Column(String)

    # ── Climate impact ────────────────────────────────────────────────────────
    climate_impact = Column(String)
    address_climate_impact = Column(String)
    impact_response = Column(String)

    # ── Relationship back to parent ───────────────────────────────────────────
    submission = relationship(
        "Submission",
        back_populates="adaptations",
    )


# ──────────────────────────────────────────────────────────────────────────────
# Mitigation (child of Submission)
# ──────────────────────────────────────────────────────────────────────────────


class Mitigation(Base):
    """Mitigation-specific details for a submission."""

    __tablename__ = "mitigation"
    __table_args__ = {"schema": "nccrd"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    submission_id = Column(
        UUID(as_uuid=True),
        ForeignKey("nccrd.submission.id"),
        nullable=False,
    )

    # ── Sector classification ─────────────────────────────────────────────────
    sector = Column(String)
    subsector = Column(String)
    secondary = Column(String)

    # ── Project type ──────────────────────────────────────────────────────────
    project_type = Column(String)
    project_subtype = Column(String)

    # ── Policy linkages ───────────────────────────────────────────────────────
    mitigation_program = Column(String)
    national_policy = Column(String)
    provincial_municipal = Column(String)
    primary_intended_outcome = Column(String)

    # ── Progress ──────────────────────────────────────────────────────────────
    progress_calculator = Column(String)

    # ── Co-benefits ───────────────────────────────────────────────────────────
    environmental_co_benefit = Column(String)          # Fixed typo: was ``enviromental_co_benefit``.
    environmental_co_benefit_description = Column(String)
    social_co_benefit = Column(String)
    social_co_benefit_description = Column(String)
    economic_co_benefit = Column(String)
    economic_co_benefit_description = Column(String)

    # ── Carbon credit information ─────────────────────────────────────────────
    carbon_credit = Column(String)
    cdm_voluntary = Column(String)
    cdm_executive_board_status = Column(String)
    cdm_methodology = Column(String)
    organization_issuing_credits = Column(String)
    voluntary_methodology = Column(String)
    cdm_project_number = Column(String)

    # ── Relationship back to parent ───────────────────────────────────────────
    submission = relationship(
        "Submission",
        back_populates="mitigations",
    )


# ──────────────────────────────────────────────────────────────────────────────
# ProgressReport (MRV documents — one-to-many with Submission)
# ──────────────────────────────────────────────────────────────────────────────


class ProgressReport(Base):
    """
    Monitoring, Reporting & Verification (MRV) document attached to a
    Submission.  Stores a reference URL rather than the binary itself so that
    files can be hosted on object storage (S3, Azure Blob, etc.).
    """

    __tablename__ = "progress_report"
    __table_args__ = {"schema": "nccrd"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    submission_id = Column(
        UUID(as_uuid=True),
        ForeignKey("nccrd.submission.id"),
        nullable=False,
    )

    file_url = Column(String, nullable=False)
    file_name = Column(String, nullable=False)
    upload_date = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text)

    # ── Relationship back to parent ───────────────────────────────────────────
    submission = relationship(
        "Submission",
        back_populates="progress_reports",
    )
