"""
Pydantic v1 schemas for the NCCRD submission API.

Changelog vs. previous version
--------------------------------
* ``AdaptaionCreate``  →  ``AdaptationCreate``  (typo corrected).
* ``enviromental_co_benefit``  →  ``environmental_co_benefit``  (both Create
  and Response schemas for Mitigation).
* Removed ``project_manager_position``, ``project_manager_phone``, and
  ``project_manager_mobile``; replaced with ``project_manager_contact_number``.
* ``geo_location`` is now a strict ``GeoLocationSchema`` model instead of a
  plain ``Dict``, enforcing the full geographic hierarchy plus coordinate
  range validation.
* ``SubmissionCreate`` and ``SubmissionUpdate`` use Python-enum-backed fields
  (``InterventionMeasurementEnum``, ``ImplementationStatusEnum``,
  ``FundingTypeEnum``) so bad values are rejected at the API boundary.
* New ``ProgressReportCreate`` / ``ProgressReportResponse`` schemas to handle
  MRV file tracking.
* ``SubmissionResponse`` now includes an optional ``progress_reports`` list.
"""

from __future__ import annotations

import enum
import re
from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, validator


# ──────────────────────────────────────────────────────────────────────────────
# Enum types (mirror DB-level enums; single source of truth)
# ──────────────────────────────────────────────────────────────────────────────


class InterventionMeasurementEnum(str, enum.Enum):
    """Allowed values for ``intervention_measurement``."""

    MITIGATION = "Mitigation"
    ADAPTATION = "Adaptation"
    CROSS_CUTTING = "Cross Cutting"


class ImplementationStatusEnum(str, enum.Enum):
    """Allowed values for ``implementation_status``."""

    PLANNED = "Planned"
    UNDER_IMPLEMENTATION = "Under Implementation"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"
    ON_HOLD = "On Hold"


class FundingTypeEnum(str, enum.Enum):
    """Allowed values for ``funding_type``."""

    GRANT = "Grant"
    LOAN = "Loan"
    OWN_FUNDING = "Own Funding"
    PUBLIC_PRIVATE = "Public-Private Partnership"
    NONE = "None"
    OTHER = "Other"


# ──────────────────────────────────────────────────────────────────────────────
# Geo-location schema (strict hierarchy + coordinate validation)
# ──────────────────────────────────────────────────────────────────────────────


class GeoLocationSchema(BaseModel):
    """
    Strict geographic location for a submission.

    Enforces the full administrative hierarchy used by the NCCRD
    (country → province → district → local municipality → town/suburb)
    together with an optional GeoJSON Point geometry.
    """

    country: Optional[str] = Field(
        None,
        description="ISO 3166-1 alpha-3 country code, e.g. 'ZAF'.",
    )
    province: str = Field(
        ...,
        description="Province code as used in the regional reference tables, e.g. 'GT'.",
    )
    district: Optional[str] = Field(
        None,
        description="District municipality code, e.g. 'DC48'.",
    )
    local_municipality: Optional[str] = Field(
        None,
        description="Local municipality code, e.g. 'GT484'.",
    )
    town_suburb: Optional[str] = Field(
        None,
        description="Town or suburb name.",
    )
    type: str = Field(
        "Point",
        description="GeoJSON geometry type (currently only 'Point' is supported).",
    )
    coordinates: Optional[List[float]] = Field(
        None,
        description="[longitude, latitude] decimal degree pair.",
        min_items=2,
        max_items=2,
    )

    @validator("coordinates")
    @classmethod
    def validate_coordinates(cls, v: Optional[List[float]]) -> Optional[List[float]]:
        """Reject coordinates outside valid WGS-84 ranges."""
        if v is not None:
            lon, lat = v
            if not (-180.0 <= lon <= 180.0):
                raise ValueError(
                    f"Longitude {lon} is out of range [-180, 180]."
                )
            if not (-90.0 <= lat <= 90.0):
                raise ValueError(
                    f"Latitude {lat} is out of range [-90, 90]."
                )
        return v

    class Config:
        schema_extra = {
            "example": {
                "country": "ZAF",
                "province": "GT",
                "district": "DC48",
                "local_municipality": "GT484",
                "town_suburb": "Barberton",
                "type": "Point",
                "coordinates": [30.374, -27.936],
            }
        }


# ──────────────────────────────────────────────────────────────────────────────
# Progress Report (MRV) schemas
# ──────────────────────────────────────────────────────────────────────────────


class ProgressReportCreate(BaseModel):
    """Input schema for attaching a progress / MRV document to a submission."""

    file_url: str = Field(
        ...,
        description="Publicly accessible (or pre-signed) URL to the stored document.",
    )
    file_name: str = Field(
        ...,
        description="Original file name as uploaded by the user.",
    )
    notes: Optional[str] = Field(
        None,
        description="Free-text notes or summary for this report.",
    )

    class Config:
        schema_extra = {
            "example": {
                "file_url": "https://storage.example.com/reports/mrv-2024-q1.pdf",
                "file_name": "mrv-2024-q1.pdf",
                "notes": "Q1 2024 monitoring report.",
            }
        }


class ProgressReportResponse(BaseModel):
    """Output schema for a stored progress / MRV document."""

    id: int
    submission_id: UUID
    file_url: str
    file_name: str
    upload_date: Optional[datetime] = None
    notes: Optional[str] = None

    class Config:
        orm_mode = True


# ──────────────────────────────────────────────────────────────────────────────
# Mitigation schemas
# ──────────────────────────────────────────────────────────────────────────────


class MitigationCreate(BaseModel):
    """Input schema for creating mitigation-specific data."""

    sector: str = Field(..., description="Primary sector for the mitigation intervention.")
    subsector: Optional[str] = Field(None)
    secondary: Optional[str] = Field(None)
    project_type: Optional[str] = Field(None)
    project_subtype: Optional[str] = Field(None)
    mitigation_program: Optional[str] = Field(None)
    national_policy: Optional[str] = Field(None)
    provincial_municipal: Optional[str] = Field(None)
    primary_intended_outcome: Optional[str] = Field(None)
    progress_calculator: Optional[str] = Field(None)

    # Fixed typo: was ``enviromental_co_benefit``.
    environmental_co_benefit: Optional[str] = Field(None)
    environmental_co_benefit_description: Optional[str] = Field(None)
    social_co_benefit: Optional[str] = Field(None)
    social_co_benefit_description: Optional[str] = Field(None)
    economic_co_benefit: Optional[str] = Field(None)
    economic_co_benefit_description: Optional[str] = Field(None)

    carbon_credit: Optional[str] = Field(None)
    cdm_voluntary: Optional[str] = Field(None)
    cdm_executive_board_status: Optional[str] = Field(None)
    cdm_methodology: Optional[str] = Field(None)
    organization_issuing_credits: Optional[str] = Field(None)
    voluntary_methodology: Optional[str] = Field(None)
    cdm_project_number: Optional[str] = Field(None)

    class Config:
        schema_extra = {
            "example": {
                "sector": "Energy",
                "subsector": "Renewable",
                "secondary": "Solar",
                "project_type": "Infrastructure",
                "project_subtype": "Solar Farm",
                "mitigation_program": "Emission Reduction Initiative",
                "national_policy": "National Energy Policy",
                "provincial_municipal": "City of Cape Town",
                "primary_intended_outcome": "Reduce emissions by 30% by 2030",
                "progress_calculator": "Milestone-based approach",
                "environmental_co_benefit": "Biodiversity",
                "environmental_co_benefit_description": "Enhanced local biodiversity",
                "social_co_benefit": "Community upliftment",
                "social_co_benefit_description": "Employment opportunities",
                "economic_co_benefit": "Cost Savings",
                "economic_co_benefit_description": "Reduced energy bills",
                "carbon_credit": "Yes",
                "cdm_voluntary": "Voluntary credits",
                "cdm_executive_board_status": "Active",
                "cdm_methodology": "Methodology XYZ",
                "organization_issuing_credits": "Green Credits Org",
                "voluntary_methodology": "Voluntary Method ABC",
                "cdm_project_number": "CDM12345",
            }
        }


class MitigationResponse(BaseModel):
    """Output schema for mitigation data returned from the API."""

    sector: Optional[str] = None
    subsector: Optional[str] = None
    secondary: Optional[str] = None
    project_type: Optional[str] = None
    project_subtype: Optional[str] = None
    mitigation_program: Optional[str] = None
    national_policy: Optional[str] = None
    provincial_municipal: Optional[str] = None
    primary_intended_outcome: Optional[str] = None
    progress_calculator: Optional[str] = None
    environmental_co_benefit: Optional[str] = None
    environmental_co_benefit_description: Optional[str] = None
    social_co_benefit: Optional[str] = None
    social_co_benefit_description: Optional[str] = None
    economic_co_benefit: Optional[str] = None
    economic_co_benefit_description: Optional[str] = None
    carbon_credit: Optional[str] = None
    cdm_voluntary: Optional[str] = None
    cdm_executive_board_status: Optional[str] = None
    cdm_methodology: Optional[str] = None
    organization_issuing_credits: Optional[str] = None
    voluntary_methodology: Optional[str] = None
    cdm_project_number: Optional[str] = None

    class Config:
        orm_mode = True


# ──────────────────────────────────────────────────────────────────────────────
# Adaptation schemas
# ──────────────────────────────────────────────────────────────────────────────


class AdaptationCreate(BaseModel):
    """
    Input schema for creating adaptation-specific data.
    Previously named ``AdaptaionCreate`` (typo corrected).
    """

    sector: str = Field(..., description="Primary sector for the adaptation intervention.")
    national_policy: Optional[str] = Field(None)
    intervention_goal: Optional[str] = Field(None)
    provincial_municipal: Optional[str] = Field(None)
    hazard: Optional[str] = Field(None)
    progress_calculator: Optional[str] = Field(None)
    climate_impact: Optional[str] = Field(None)
    address_climate_impact: Optional[str] = Field(None)
    impact_response: Optional[str] = Field(None)

    class Config:
        schema_extra = {
            "example": {
                "sector": "Environment",
                "national_policy": "National Biodiversity Strategy",
                "intervention_goal": "Conservation",
                "provincial_municipal": "City of Cape Town",
                "hazard": "Invasive Species",
                "progress_calculator": "Progress details here",
                "climate_impact": "Low impact",
                "address_climate_impact": "Mitigation measures planned",
                "impact_response": "Ongoing response",
            }
        }


class AdaptationResponse(BaseModel):
    """Output schema for adaptation data returned from the API."""

    sector: Optional[str] = None
    national_policy: Optional[str] = None
    intervention_goal: Optional[str] = None
    provincial_municipal: Optional[str] = None
    hazard: Optional[str] = None
    progress_calculator: Optional[str] = None
    climate_impact: Optional[str] = None
    address_climate_impact: Optional[str] = None
    impact_response: Optional[str] = None

    class Config:
        orm_mode = True


# ──────────────────────────────────────────────────────────────────────────────
# Submission schemas
# ──────────────────────────────────────────────────────────────────────────────


class SubmissionCreate(BaseModel):
    """
    Input schema for creating a new submission.

    Enum-typed fields (``intervention_measurement``, ``implementation_status``,
    ``funding_type``) are validated at the API boundary; invalid values are
    rejected with a 422 Unprocessable Entity error.
    ``geo_location`` must now conform to the strict ``GeoLocationSchema``.
    """

    title: str = Field(..., description="Project title.")
    intervention_measurement: InterventionMeasurementEnum = Field(
        ...,
        description=(
            "Intervention measurement type. "
            "Allowed values: 'Mitigation', 'Adaptation', or 'Cross Cutting'."
        ),
    )
    description: Optional[str] = None
    implementation_status: Optional[ImplementationStatusEnum] = None
    implementation_organization: str = Field(
        ..., description="Organization implementing the project."
    )
    implementation_partners_other: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    link: Optional[str] = None

    # ── Funding ───────────────────────────────────────────────────────────────
    funding_organization: Optional[str] = None
    funding_type: Optional[FundingTypeEnum] = None
    funding_amount: Optional[float] = None
    estimated_budget_cost: Optional[str] = None

    # ── Location ──────────────────────────────────────────────────────────────
    geo_location: GeoLocationSchema = Field(
        ...,
        description="Strict geographic location following the NCCRD hierarchy.",
    )

    # ── Project manager ───────────────────────────────────────────────────────
    project_manager_name: str = Field(..., description="Project manager's full name.")
    project_manager_organization: Optional[str] = None
    project_manager_email: str = Field(..., description="Project manager's email address.")
    # Merged from project_manager_phone + project_manager_mobile.
    project_manager_contact_number: Optional[str] = Field(
        None,
        description="Phone or mobile contact number for the project manager.",
    )

    # ── Misc ──────────────────────────────────────────────────────────────────
    research: Optional[str] = None
    platform: Optional[str] = None
    data_source: Optional[str] = None

    # ── Nested child payloads ─────────────────────────────────────────────────
    mitigation_data: Optional[MitigationCreate] = Field(
        None,
        description=(
            "Mitigation-specific details. "
            "Required when intervention_measurement is 'Mitigation' or 'Cross Cutting'."
        ),
    )
    adaptation_data: Optional[AdaptationCreate] = Field(
        None,
        description=(
            "Adaptation-specific details. "
            "Required when intervention_measurement is 'Adaptation' or 'Cross Cutting'."
        ),
    )

    @validator("project_manager_email")
    @classmethod
    def validate_project_manager_email(cls, v: str) -> str:
        """Reject obviously-malformed email addresses."""
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
            raise ValueError(f"'{v}' is not a valid email address.")
        return v

    class Config:
        use_enum_values = True
        schema_extra = {
            "example": {
                "title": "Mpu Barbeton IAP Control Programme",
                "intervention_measurement": "Cross Cutting",
                "description": (
                    "This programme aims to improve the integrity of natural resources "
                    "by preventing the introduction of new invasive alien species."
                ),
                "implementation_status": "Under Implementation",
                "implementation_organization": "DFFE",
                "implementation_partners_other": "N/A",
                "start_date": "2021-01-01T00:00:00Z",
                "end_date": "2025-12-31T00:00:00Z",
                "link": "https://example.com",
                "funding_organization": "Expanded Public Works Programme",
                "funding_type": "Grant",
                "funding_amount": 537841.67,
                "estimated_budget_cost": "R500k – R1m",
                "geo_location": {
                    "country": "ZAF",
                    "province": "GT",
                    "district": "DC48",
                    "local_municipality": "GT484",
                    "town_suburb": "Barberton",
                    "type": "Point",
                    "coordinates": [30.374, -27.936],
                },
                "project_manager_name": "Gladys Nyundu",
                "project_manager_organization": "DFFE",
                "project_manager_email": "gnyundu@environment.gov.za",
                "project_manager_contact_number": "0821234567",
                "research": "Preliminary research completed.",
                "platform": "API",
                "mitigation_data": {
                    "sector": "Energy",
                    "subsector": "Renewable",
                    "environmental_co_benefit": "Biodiversity",
                },
                "adaptation_data": {
                    "sector": "Environment",
                    "hazard": "Invasive Species",
                },
            }
        }


class SubmissionUpdate(BaseModel):
    """
    Schema for partial updates to an existing submission.
    All fields are optional; only supplied fields are updated.
    """

    title: Optional[str] = None
    intervention_measurement: Optional[InterventionMeasurementEnum] = None
    description: Optional[str] = None
    implementation_status: Optional[ImplementationStatusEnum] = None
    implementation_organization: Optional[str] = None
    implementation_partners_other: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    link: Optional[str] = None

    funding_organization: Optional[str] = None
    funding_type: Optional[FundingTypeEnum] = None
    funding_amount: Optional[float] = None
    estimated_budget_cost: Optional[str] = None

    geo_location: Optional[GeoLocationSchema] = None

    project_manager_name: Optional[str] = None
    project_manager_organization: Optional[str] = None
    project_manager_email: Optional[str] = None
    project_manager_contact_number: Optional[str] = None

    submission_status: Optional[str] = None
    submission_comments: Optional[str] = None
    issubmitted: Optional[bool] = None
    research: Optional[str] = None

    # Metadata fields that can be updated by administrative processes.
    createdby: Optional[int] = None
    createdate: Optional[datetime] = None
    updatedate: Optional[datetime] = None
    updatedby: Optional[int] = None
    deletedby: Optional[int] = None
    deletedate: Optional[datetime] = None
    deleted: Optional[bool] = None

    mitigation_data: Optional[MitigationCreate] = None
    adaptation_data: Optional[AdaptationCreate] = None

    class Config:
        use_enum_values = True
        schema_extra = {
            "example": {
                "title": "Mpu Barbeton IAP Control – Revised",
                "description": "Revised description with updated research findings.",
                "implementation_status": "Completed",
                "issubmitted": True,
                "updatedate": "2025-06-01T12:00:00Z",
                "mitigation_data": {
                    "sector": "Energy",
                    "primary_intended_outcome": "30% emission reduction achieved",
                },
            }
        }


class SubmissionModel(BaseModel):
    """ORM-compatible schema for internal database layer interaction."""

    _id: int
    id: UUID
    title: Optional[str] = None
    intervention_measurement: Optional[str] = None
    description: Optional[str] = None
    implementation_status: Optional[str] = None
    implementation_organization: Optional[str] = None
    implementation_partners_other: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    link: Optional[str] = None
    funding_organization: Optional[str] = None
    funding_type: Optional[str] = None
    funding_amount: Optional[float] = None
    estimated_budget_cost: Optional[str] = None
    geo_location: Optional[Any] = None
    project_manager_name: Optional[str] = None
    project_manager_organization: Optional[str] = None
    project_manager_email: Optional[str] = None
    project_manager_contact_number: Optional[str] = None
    submission_status: Optional[str] = None
    submission_comments: Optional[str] = None
    issubmitted: Optional[bool] = False
    research: Optional[str] = None
    data_source: Optional[str] = None
    createdby: Optional[int] = None
    createdate: Optional[datetime] = None
    updatedate: Optional[datetime] = None
    updatedby: Optional[int] = None
    deletedby: Optional[int] = None
    deletedate: Optional[datetime] = None
    deleted: Optional[bool] = False

    class Config:
        orm_mode = True


class SubmissionResponse(BaseModel):
    """
    Full API response schema for a single submission, including optional
    nested Mitigation, Adaptation, and ProgressReport records.
    """

    id: UUID
    title: Optional[str] = None
    intervention_measurement: Optional[str] = None
    description: Optional[str] = None
    implementation_status: Optional[str] = None
    implementation_organization: Optional[str] = None
    implementation_partners_other: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    link: Optional[str] = None
    funding_organization: Optional[str] = None
    funding_type: Optional[str] = None
    funding_amount: Optional[float] = None
    estimated_budget_cost: Optional[str] = None
    geo_location: Optional[Any] = None   # Returned as a raw dict for GeoJSON flexibility.
    project_manager_name: Optional[str] = None
    project_manager_organization: Optional[str] = None
    project_manager_email: Optional[str] = None
    project_manager_contact_number: Optional[str] = None
    submission_status: Optional[str] = None
    submission_comments: Optional[str] = None
    issubmitted: Optional[bool] = None
    research: Optional[str] = None
    data_source: Optional[str] = None
    createdby: Optional[int] = None
    createdate: Optional[datetime] = None
    updatedate: Optional[datetime] = None
    updatedby: Optional[int] = None
    deletedby: Optional[int] = None
    deletedate: Optional[datetime] = None
    deleted: Optional[bool] = None

    # Nested child responses.
    progress_reports: Optional[List[ProgressReportResponse]] = None
    mitigation: Optional[MitigationResponse] = None
    adaptation: Optional[AdaptationResponse] = None

    class Config:
        orm_mode = True
