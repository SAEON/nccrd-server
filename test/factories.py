from random import randint, choice
import uuid

import factory
from factory.alchemy import SQLAlchemyModelFactory
from faker import Faker
from sqlalchemy.orm import scoped_session, sessionmaker

import nccrd.db

FactorySession = scoped_session(sessionmaker(
    bind=nccrd.db.engine,
    autocommit=False,
    autoflush=False,
    future=True,
))

fake = Faker()


class NCCRDModelFactory(SQLAlchemyModelFactory):
    class Meta:
        sqlalchemy_session = FactorySession
        sqlalchemy_session_persistence = 'commit'

class SubmissionFactory(NCCRDModelFactory):
    class Meta:
        model = nccrd.db.models.Submission

    id = factory.Sequence(lambda n: n + 1)
    name = factory.Faker('name')
    description = factory.Faker('text')
    status = factory.Iterator(['pending', 'completed', 'failed'])
    created_at = factory.Faker('date_time_this_year')
    updated_at = factory.Faker('date_time_this_year')
    user_id = factory.Sequence(lambda n: n + 1)  # Assuming user_id is an integer
    # Add any additional fields or methods here if needed

class MitigationFactory(NCCRDModelFactory):
    class Meta:
        model = nccrd.db.models.Mitigation

    id = factory.Sequence(lambda n: n + 1)
    submission_id = factory.LazyAttribute(lambda _: str(uuid.uuid4()))
    sector = factory.Faker('word')
    subsector = factory.Faker('word')
    secondary = factory.Faker('word')
    project_type = factory.Faker('word')
    project_subtype = factory.Faker('word')
    mitigation_program = factory.Faker('word')
    national_policy = factory.Faker('word')
    provincial_municipal = factory.Faker('word')
    primary_intended_outcome = factory.Faker('word')
    progress_calculator = factory.Faker('word')
    enviromental_co_benefit = factory.Faker('word')
    enviromental_co_benefit_description = factory.Faker('sentence')
    social_co_benefit = factory.Faker('word')
    social_co_benefit_description = factory.Faker('sentence')
    economic_co_benefit = factory.Faker('word')
    economic_co_benefit_description = factory.Faker('sentence')
    carbon_credit = factory.Faker('word')
    cdm_voluntary = factory.Faker('word')
    cdm_executive_board_status = factory.Faker('word')
    cdm_methodology = factory.Faker('word')
    organization_issuing_credits = factory.Faker('company')
    voluntary_methodology = factory.Faker('word')
    cdm_project_number = factory.Faker('bothify', text='CDM#####')

class AdaptaionFactory(NCCRDModelFactory):
    class Meta:
        model = nccrd.db.models.Adaptaion

    id = factory.Sequence(lambda n: n + 1)
    submission_id = factory.LazyAttribute(lambda _: str(uuid.uuid4()))
    sector = factory.Faker('word')
    national_policy = factory.Faker('word')
    intervention_goal = factory.Faker('sentence')
    provincial_municipal = factory.Faker('word')
    hazard = factory.Faker('word')
    progress_calculator = factory.Faker('sentence')
    climate_impact = factory.Faker('sentence')
    address_climate_impact = factory.Faker('sentence')
    impact_response = factory.Faker('sentence')