from sqlalchemy import Column, Integer, String, JSON,DateTime,Float,Boolean,ForeignKey
from nccrd.db import Base
from sqlalchemy.dialects.postgresql import UUID
import uuid

class Submission(Base):

    __tablename__ = "submission"
    __table_args__ = {"schema": "nccrd"}
    _id = Column(Integer, primary_key=True, autoincrement=True)
    id = Column(UUID(as_uuid=True), unique=True, default=uuid.uuid4, nullable=False)

    # Project Overview
    title = Column(String)
    intervention_measurement = Column(String)
    description = Column(String)
    implementation_status = Column(String)
    implementation_organization = Column(String)
    implementation_partners_other = Column(String)
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    link = Column(String)

    # Project Funding
    funding_organization = Column(String)
    funding_type = Column(String)
    funding_amount = Column(Float)
    estimated_budget_cost = Column(String)

    # Geographic location(s)
    geo_location = Column(JSON)

    # Project Manager
    project_manager_name = Column(String)
    project_manager_organization = Column(String)
    project_manager_position = Column(String)
    project_manager_email = Column(String)
    project_manager_phone = Column(String)
    project_manager_mobile = Column(String)

    # Submission status
    submission_status = Column(String)
    submission_comments = Column(String)
    issubmitted = Column(Boolean)

    # Project Research
    research = Column(String)

    # Metadata
    createdby = Column(Integer)
    createdate = Column(DateTime)
    updatedate = Column(DateTime)
    updatedby = Column(Integer)
    deletedby = Column(Integer)
    deletedate = Column(DateTime)
    deleted = Column(Boolean)

class Adaptaion(Base):
    __tablename__ = "adaptaion"
    __table_args__ = {"schema": "nccrd"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    #Adaptation details
    submission_id = Column(UUID(as_uuid=True), ForeignKey("nccrd.submission.id"), nullable=False)
    sector = Column(String)
    national_policy = Column(String)
    intervention_goal = Column(String)
    provincial_municipal = Column(String)
    hazard = Column(String)

    #Progress Calculator
    progress_calculator =  Column(String)

    #climate impact
    climate_impact = Column(String)
    address_climate_impact = Column(String)
    impact_response = Column(String)

    #progress reports



class Mitigation(Base):
    __tablename__ = "mitigation"
    __table_args__ = {"schema": "nccrd"}

    id = Column(Integer, primary_key=True)

    submission_id = Column(UUID(as_uuid=True), ForeignKey("nccrd.submission.id"), nullable=False)

    # Mitigation details
    sector = Column(String) #main,
    subsector = Column(String)
    secondary = Column(String)

    #project type
    project_type = Column(String)
    project_subtype = Column(String)

    #Policy
    mitigation_program = Column(String)
    national_policy =  Column(String)
    provincial_municipal = Column(String)
    primary_intended_outcome = Column(String)

    # Progress Calculator
    progress_calculator =  Column(String)

    # co-benefit information
    enviromental_co_benefit =  Column(String)
    enviromental_co_benefit_description = Column(String)
    social_co_benefit =  Column(String)
    social_co_benefit_description = Column(String)
    economic_co_benefit =  Column(String)
    economic_co_benefit_description = Column(String)

    # Carbon credit information
    carbon_credit= Column(Boolean)
    cdm_voluntary = Column(String)
    cdm_executive_board_status = Column(String)
    cdm_methodology = Column(String)
    organization_issuing_credits =  Column(String)
    voluntary_methodology = Column(String)
    cdm_project_number = Column(String)