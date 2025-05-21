from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict,Any
from uuid import UUID

# Schemas for Mitigation data
class MitigationCreate(BaseModel):
    sector: str = Field(..., description="Primary sector for the mitigation intervention")
    subsector: Optional[str] = Field(None)
    secondary: Optional[str] = Field(None)
    project_type: Optional[str] = Field(None)
    project_subtype: Optional[str] = Field(None)
    mitigation_program: Optional[str] = Field(None)
    national_policy: Optional[str] = Field(None)
    provincial_municipal: Optional[str] = Field(None)
    primary_intended_outcome: Optional[str] = Field(None)
    progress_calculator: Optional[str] = Field(None)
    enviromental_co_benefit: Optional[str] = Field(None)
    enviromental_co_benefit_description: Optional[str] = Field(None)
    social_co_benefit: Optional[str] = Field(None)
    social_co_benefit_description: Optional[str] = Field(None)
    economic_co_benefit: Optional[str] = Field(None)
    economic_co_benefit_description: Optional[str] = Field(None)
    carbon_credit: Optional[bool] = Field(None)
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
                "primary_intended_outcome": "Reduce emissions",
                "progress_calculator": "Milestone-based approach",
                "enviromental_co_benefit": "Biodiversity",
                "enviromental_co_benefit_description": "Enhanced local biodiversity",
                "social_co_benefit": "Community upliftment",
                "social_co_benefit_description": "Employment opportunities",
                "economic_co_benefit": "Cost Savings",
                "economic_co_benefit_description": "Reduced energy bills",
                "carbon_credit": True,
                "cdm_voluntary": "Voluntary credits",
                "cdm_executive_board_status": "Active",
                "cdm_methodology": "Methodology XYZ",
                "organization_issuing_credits": "Green Credits Org",
                "voluntary_methodology": "Voluntary Method ABC",
                "cdm_project_number": "CDM12345"
            }
        }

# Schema for Adaptation data
class AdaptaionCreate(BaseModel):
    sector: str = Field(..., description="Primary sector for the adaptation intervention")
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
                "impact_response": "Ongoing response"
            }
        }

# Schema for creating a Submission
class SubmissionCreate(BaseModel):
    title: str = Field(..., description="Project title")
    intervention_measurement: str = Field(
        ...,
        description=(
            "Intervention measurement type. Allowed values: 'Mitigation', 'Adaptation', or 'Cross Cutting'."
        ),
    )
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

    geo_location: Optional[Dict] = Field(None, description="GeoJSON for location")

    project_manager_name: Optional[str] = None
    project_manager_organization: Optional[str] = None
    project_manager_position: Optional[str] = None
    project_manager_email: Optional[str] = None
    project_manager_phone: Optional[str] = None
    project_manager_mobile: Optional[str] = None

    submission_status: Optional[str] = None
    submission_comments: Optional[str] = None
    issubmitted: Optional[bool] = Field(False)
    research: Optional[str] = None

    createdby: Optional[int] = None
    createdate: Optional[datetime] = None
    updatedate: Optional[datetime] = None
    updatedby: Optional[int] = None
    deletedby: Optional[int] = None
    deletedate: Optional[datetime] = None
    deleted: Optional[bool] = Field(False)

    # Nested records for related interventions.
    mitigation_data: Optional[MitigationCreate] = Field(
        None,
        description="Mitigation-specific details. Required if intervention_measurement is 'Mitigation' or 'Cross Cutting'."
    )
    adaptation_data: Optional[AdaptaionCreate] = Field(
        None,
        description="Adaptation-specific details. Required if intervention_measurement is 'Adaptation' or 'Cross Cutting'."
    )

    class Config:
        schema_extra = {
            "example": {
                "title": "Mpu Barbeton",
                "intervention_measurement": "Cross Cutting",
                "description": (
                    "This programme aims to improve the integrity of natural resources by preventing the introduction of new "
                    "invasive species; undertaking early detection of and rapid response to emerging invasive alien species; and, "
                    "containing the impact of established invasive alien species. These are achieved through integrated prevention "
                    "and control methods, supported by incentives, disincentives, advocacy and research."
                ),
                "implementation_status": "Under Implementation",
                "implementation_organization": "N/A",
                "implementation_partners_other": "N/A",
                "start_date": "2021-01-01T00:00:00Z",
                "end_date": "2025-12-31T00:00:00Z",
                "link": "N/A",
                "funding_organization": "Expanded Public Works Programme",
                "funding_type": "NONE",
                "funding_amount": 537841.67,
                "estimated_budget_cost": "NONE",
                "geo_location": {"type": "Point", "coordinates": [30.374, -27.936]},
                "project_manager_name": "Gladys Nyundu",
                "project_manager_organization": "N/A",
                "project_manager_position": "N/A",
                "project_manager_email": "Gnyundu@enviroment.gov.za",
                "project_manager_phone": "N/A",
                "project_manager_mobile": "N/A",
                "submission_status": "Accepted",
                "submission_comments": "Project accepted",
                "issubmitted": True,
                "research": "Preliminary research completed.",
                "createdby": 35,
                "createdate": "2021-11-09T19:59:00Z",
                "updatedate": "2025-04-24T20:00:00Z",
                "updatedby": 35,
                "deletedby": None,
                "deletedate": None,
                "deleted": False,
                "mitigation_data": {
                    "sector": "Energy",
                    "subsector": "Renewable",
                    "secondary": "Solar",
                    "project_type": "Infrastructure",
                    "project_subtype": "Solar Farm",
                    "mitigation_program": "Emission Reduction Initiative",
                    "national_policy": "National Energy Policy",
                    "provincial_municipal": "City of Cape Town",
                    "primary_intended_outcome": "Reduce emissions",
                    "progress_calculator": "Milestone-based",
                    "enviromental_co_benefit": "Biodiversity",
                    "enviromental_co_benefit_description": "Enhanced local biodiversity",
                    "social_co_benefit": "Community upliftment",
                    "social_co_benefit_description": "Employment opportunities",
                    "economic_co_benefit": "Cost Savings",
                    "economic_co_benefit_description": "Reduced energy bills",
                    "carbon_credit": True,
                    "cdm_voluntary": "Voluntary credits",
                    "cdm_executive_board_status": "Active",
                    "cdm_methodology": "Methodology XYZ",
                    "organization_issuing_credits": "Green Credits Org",
                    "voluntary_methodology": "Voluntary Method ABC",
                    "cdm_project_number": "CDM12345"
                },
                "adaptation_data": {
                    "sector": "Environment",
                    "national_policy": "National Biodiversity Strategy",
                    "intervention_goal": "Conservation",
                    "provincial_municipal": "City of Cape Town",
                    "hazard": "Invasive Species",
                    "progress_calculator": "Progress details here",
                    "climate_impact": "Low impact",
                    "address_climate_impact": "Mitigation measures planned",
                    "impact_response": "Ongoing response"
                }
            }
        }

# Schema for updating a Submission.
class SubmissionUpdate(BaseModel):
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

    geo_location: Optional[Dict] = None

    project_manager_name: Optional[str] = None
    project_manager_organization: Optional[str] = None
    project_manager_position: Optional[str] = None
    project_manager_email: Optional[str] = None
    project_manager_phone: Optional[str] = None
    project_manager_mobile: Optional[str] = None

    submission_status: Optional[str] = None
    submission_comments: Optional[str] = None
    issubmitted: Optional[bool] = None
    research: Optional[str] = None

    createdby: Optional[int] = None
    createdate: Optional[datetime] = None
    updatedate: Optional[datetime] = None
    updatedby: Optional[int] = None
    deletedby: Optional[int] = None
    deletedate: Optional[datetime] = None
    deleted: Optional[bool] = None

    mitigation_data: Optional[MitigationCreate] = None
    adaptation_data: Optional[AdaptaionCreate] = None

    class Config:
        schema_extra = {
            "example": {
                "title": "Mpu Barbeton - Revised",
                "description": "Revised description with updated research findings.",
                "submission_status": "Accepted",
                "issubmitted": True,
                "updatedate": "2025-06-01T12:00:00Z",
                "mitigation_data": {
                    "sector": "Energy",
                    "subsector": "Renewable",
                    "secondary": "Solar",
                    "project_type": "Infrastructure",
                    "project_subtype": "Solar Farm",
                    "mitigation_program": "Emission Reduction Initiative",
                    "national_policy": "National Energy Policy",
                    "provincial_municipal": "City of Cape Town",
                    "primary_intended_outcome": "Reduce emissions",
                    "progress_calculator": "Milestone-based",
                    "enviromental_co_benefit": "Biodiversity",
                    "enviromental_co_benefit_description": "Enhanced local biodiversity",
                    "social_co_benefit": "Community upliftment",
                    "social_co_benefit_description": "Employment opportunities",
                    "economic_co_benefit": "Cost Savings",
                    "economic_co_benefit_description": "Reduced energy bills",
                    "carbon_credit": True,
                    "cdm_voluntary": "Voluntary credits",
                    "cdm_executive_board_status": "Active",
                    "cdm_methodology": "Methodology XYZ",
                    "organization_issuing_credits": "Green Credits Org",
                    "voluntary_methodology": "Voluntary Method ABC",
                    "cdm_project_number": "CDM12345"
                },
                "adaptation_data": {
                    "sector": "Environment",
                    "national_policy": "Revised National Biodiversity Strategy",
                    "intervention_goal": "Enhanced Conservation",
                    "provincial_municipal": "City of Cape Town",
                    "hazard": "Invasive Species",
                    "progress_calculator": "Updated progress details",
                    "climate_impact": "Moderate impact",
                    "address_climate_impact": "New mitigation measures implemented",
                    "impact_response": "Active response underway"
                }
            }
        }


class SubmissionModel(BaseModel):
    _id: int
    id: UUID
    title: str
    intervention_measurement: str
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
    geo_location: Optional[Dict] = None
    project_manager_name: Optional[str] = None
    project_manager_organization: Optional[str] = None
    project_manager_position: Optional[str] = None
    project_manager_email: Optional[str] = None
    project_manager_phone: Optional[str] = None
    project_manager_mobile: Optional[str] = None
    submission_status: Optional[str] = None
    submission_comments: Optional[str] = None
    issubmitted: Optional[bool] = False
    research: Optional[str] = None
    createdby: Optional[int] = None
    createdate: Optional[datetime] = None
    updatedate: Optional[datetime] = None
    updatedby: Optional[int] = None
    deletedby: Optional[int] = None
    deletedate: Optional[datetime] = None
    deleted: Optional[bool] = False

    class Config:
        orm_mode = True



class MitigationResponse(BaseModel):
    sector: Optional[str]
    subsector: Optional[str]
    secondary: Optional[str]
    project_type: Optional[str]
    project_subtype: Optional[str]
    mitigation_program: Optional[str]
    national_policy: Optional[str]
    provincial_municipal: Optional[str]
    primary_intended_outcome: Optional[str]
    progress_calculator: Optional[str]
    enviromental_co_benefit: Optional[str]
    enviromental_co_benefit_description: Optional[str]
    social_co_benefit: Optional[str]
    social_co_benefit_description: Optional[str]
    economic_co_benefit: Optional[str]
    economic_co_benefit_description: Optional[str]
    carbon_credit: Optional[bool]
    cdm_voluntary: Optional[str]
    cdm_executive_board_status: Optional[str]
    cdm_methodology: Optional[str]
    organization_issuing_credits: Optional[str]
    voluntary_methodology: Optional[str]
    cdm_project_number: Optional[str]

    class Config:
        orm_mode = True


class AdaptationResponse(BaseModel):
    sector: Optional[str]
    national_policy: Optional[str]
    intervention_goal: Optional[str]
    provincial_municipal: Optional[str]
    hazard: Optional[str]
    progress_calculator: Optional[str]
    climate_impact: Optional[str]
    address_climate_impact: Optional[str]
    impact_response: Optional[str]

    class Config:
        orm_mode = True


class SubmissionResponse(BaseModel):
    _id: int
    id: UUID
    title: Optional[str]
    intervention_measurement: Optional[str]
    description: Optional[str]
    implementation_status: Optional[str]
    implementation_organization: Optional[str]
    implementation_partners_other: Optional[str]
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    link: Optional[str]
    funding_organization: Optional[str]
    funding_type: Optional[str]
    funding_amount: Optional[float]
    estimated_budget_cost: Optional[str]
    geo_location: Optional[Any]  # Can be a dict (GeoJSON)
    project_manager_name: Optional[str]
    project_manager_organization: Optional[str]
    project_manager_position: Optional[str]
    project_manager_email: Optional[str]
    project_manager_phone: Optional[str]
    project_manager_mobile: Optional[str]
    submission_status: Optional[str]
    submission_comments: Optional[str]
    issubmitted: Optional[bool]
    research: Optional[str]
    createdby: Optional[int]
    createdate: Optional[datetime]
    updatedate: Optional[datetime]
    updatedby: Optional[int]
    deletedby: Optional[int]
    deletedate: Optional[datetime]
    deleted: Optional[bool]
    mitigation: Optional[MitigationResponse] = None
    adaptation: Optional[AdaptationResponse] = None

    class Config:
        orm_mode = True