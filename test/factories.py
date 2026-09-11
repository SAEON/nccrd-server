from datetime import datetime, timezone
import uuid

import factory
from factory.alchemy import SQLAlchemyModelFactory
from faker import Faker
from sqlalchemy.orm import scoped_session, sessionmaker

import nccrd.db
import nccrd.db.models

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

    title = factory.Faker('sentence', nb_words=6)
    intervention_measurement = factory.Iterator(['Mitigation', 'Adaptation', 'Cross Cutting'])
    description = factory.Faker('text')
    implementation_status = factory.Iterator(['Planned', 'Under Implementation', 'Completed'])
    createdate = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    issubmitted = False
    deleted = False


class MitigationFactory(NCCRDModelFactory):
    class Meta:
        model = nccrd.db.models.Mitigation

    submission_id = factory.LazyFunction(uuid.uuid4)
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
    environmental_co_benefit = factory.Faker('word')
    environmental_co_benefit_description = factory.Faker('sentence')
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


class AdaptationFactory(NCCRDModelFactory):
    class Meta:
        model = nccrd.db.models.Adaptation

    submission_id = factory.LazyFunction(uuid.uuid4)
    sector = factory.Faker('word')
    national_policy = factory.Faker('word')
    intervention_goal = factory.Faker('sentence')
    provincial_municipal = factory.Faker('word')
    hazard = factory.Faker('word')
    progress_calculator = factory.Faker('sentence')
    climate_impact = factory.Faker('sentence')
    address_climate_impact = factory.Faker('sentence')
    impact_response = factory.Faker('sentence')
