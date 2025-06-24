from nccrd.db.models import Submission, Mitigation, Adaptaion
from test import TestSession
from .factories import (
    SubmissionFactory,
    MitigationFactory,
    AdaptaionFactory
)
import uuid
from datetime import datetime

def test_submission():
    submission = SubmissionFactory()
    TestSession.add(submission)
    TestSession.commit()
    result = TestSession.query(Submission).filter_by(id=submission.id).first()
    assert result is not None
    assert result.name == submission.name
    assert result.description == submission.description

def test_mitigation():
    mitigation = MitigationFactory()
    TestSession.add(mitigation)
    TestSession.commit()
    result = TestSession.query(Mitigation).filter_by(id=mitigation.id).first()
    assert result is not None
    assert result.sector == mitigation.sector
    assert result.project_type == mitigation.project_type

def test_adaptaion():
    adaptaion = AdaptaionFactory()
    TestSession.add(adaptaion)
    TestSession.commit()
    result = TestSession.query(Adaptaion).filter_by(id=adaptaion.id).first()
    assert result is not None
    assert result.sector == adaptaion.sector
    assert result.hazard == adaptaion.hazard

def test_submission_all_fields():
    # Create a Submission with all fields populated
    submission = Submission(
        id=uuid.uuid4(),
        title='Test Submission',
        intervention_measurement='Mitigation',
        description='A test submission for all fields.',
        implementation_status='completed',
        implementation_organization='Test Org',
        implementation_partners_other='Partner Org',
        start_date=datetime(2025, 1, 1),
        end_date=datetime(2025, 12, 31),
        link='https://example.com',
        funding_organization='Funder',
        funding_type='Grant',
        funding_amount=12345.67,
        estimated_budget_cost='15000',
        geo_location={
            'country': 'ZAF',
            'province': 'GT',
            'district': 'DC48',
            'local_municipality': 'GT484',
            'type': 'Point',
            'coordinates': [30.374, -27.9363]
        },
        project_manager_name='Manager',
        project_manager_organization='Manager Org',
        project_manager_position='Lead',
        project_manager_email='manager@example.com',
        project_manager_phone='1234567890',
        project_manager_mobile='0987654321',
        submission_status='Pending',
        submission_comments='No comments',
        issubmitted=True,
        research='Research details',
        platfrom='WEB',
        createdby=1,
        createdate=datetime(2025, 6, 23),
        updatedate=datetime(2025, 6, 23),
        updatedby=1,
        deletedby=None,
        deletedate=None,
        deleted=False
    )
    TestSession.add(submission)
    TestSession.commit()

    # Create and link Mitigation
    mitigation = MitigationFactory(submission_id=submission.id)
    TestSession.add(mitigation)
    # Create and link Adaptaion
    adap = AdaptaionFactory(submission_id=submission.id)
    TestSession.add(adap)
    TestSession.commit()

    # Query and assert
    db_submission = TestSession.query(Submission).filter_by(id=submission.id).first()
    assert db_submission is not None
    assert db_submission.title == 'Test Submission'
    assert db_submission.implementation_organization == 'Test Org'
    assert db_submission.funding_amount == 12345.67
    assert db_submission.geo_location['country'] == 'ZAF'
    # Check Mitigation
    db_mitigation = TestSession.query(Mitigation).filter_by(submission_id=submission.id).first()
    assert db_mitigation is not None
    assert db_mitigation.sector is not None
    # Check Adaptaion
    db_adap = TestSession.query(Adaptaion).filter_by(submission_id=submission.id).first()
    assert db_adap is not None
    assert db_adap.sector is not None

def test_submission_required_fields():
    submission = SubmissionFactory()
    TestSession.add(submission)
    TestSession.commit()
    db_submission = TestSession.query(Submission).filter_by(id=submission.id).first()
    assert db_submission is not None
    assert db_submission.id == submission.id
    assert db_submission.title == submission.title

def test_submission_update():
    submission = SubmissionFactory()
    TestSession.add(submission)
    TestSession.commit()
    submission.title = "Updated Title"
    TestSession.commit()
    db_submission = TestSession.query(Submission).filter_by(id=submission.id).first()
    assert db_submission.title == "Updated Title"

def test_submission_delete():
    submission = SubmissionFactory()
    TestSession.add(submission)
    TestSession.commit()
    TestSession.delete(submission)
    TestSession.commit()
    db_submission = TestSession.query(Submission).filter_by(id=submission.id).first()
    assert db_submission is None

def test_mitigation_submission_relationship():
    submission = SubmissionFactory()
    TestSession.add(submission)
    TestSession.commit()
    mitigation = MitigationFactory(submission_id=submission.id)
    TestSession.add(mitigation)
    TestSession.commit()
    db_mitigation = TestSession.query(Mitigation).filter_by(id=mitigation.id).first()
    assert db_mitigation.submission_id == submission.id

def test_adaptaion_submission_relationship():
    submission = SubmissionFactory()
    TestSession.add(submission)
    TestSession.commit()
    adaptaion = AdaptaionFactory(submission_id=submission.id)
    TestSession.add(adaptaion)
    TestSession.commit()
    db_adaptaion = TestSession.query(Adaptaion).filter_by(id=adaptaion.id).first()
    assert db_adaptaion.submission_id == submission.id

def test_submission_geo_location_format():
    submission = SubmissionFactory()
    TestSession.add(submission)
    TestSession.commit()
    db_submission = TestSession.query(Submission).filter_by(id=submission.id).first()
    assert isinstance(db_submission.geo_location, dict)
    assert 'country' in db_submission.geo_location
    # Create a Submission with all fields populated
    submission = Submission(
        id=uuid.uuid4(),
        title='Test Submission',
        intervention_measurement='Mitigation',
        description='A test submission for all fields.',
        implementation_status='completed',
        implementation_organization='Test Org',
        implementation_partners_other='Partner Org',
        start_date=datetime(2025, 1, 1),
        end_date=datetime(2025, 12, 31),
        link='https://example.com',
        funding_organization='Funder',
        funding_type='Grant',
        funding_amount=12345.67,
        estimated_budget_cost='15000',
        geo_location={
            'country': 'ZAF',
            'province': 'GT',
            'district': 'DC48',
            'local_municipality': 'GT484',
            'type': 'Point',
            'coordinates': [30.374, -27.9363]
        },
        project_manager_name='Manager',
        project_manager_organization='Manager Org',
        project_manager_position='Lead',
        project_manager_email='manager@example.com',
        project_manager_phone='1234567890',
        project_manager_mobile='0987654321',
        submission_status='Pending',
        submission_comments='No comments',
        issubmitted=True,
        research='Research details',
        platfrom='WEB',
        createdby=1,
        createdate=datetime(2025, 6, 23),
        updatedate=datetime(2025, 6, 23),
        updatedby=1,
        deletedby=None,
        deletedate=None,
        deleted=False
    )
    TestSession.add(submission)
    TestSession.commit()

    # Create and link Mitigation
    mitigation = MitigationFactory(submission_id=submission.id)
    TestSession.add(mitigation)
    # Create and link Adaptaion
    adap = AdaptaionFactory(submission_id=submission.id)
    TestSession.add(adap)
    TestSession.commit()

    # Query and assert
    db_submission = TestSession.query(Submission).filter_by(id=submission.id).first()
    assert db_submission is not None
    assert db_submission.title == 'Test Submission'
    assert db_submission.implementation_organization == 'Test Org'
    assert db_submission.funding_amount == 12345.67
    assert db_submission.geo_location['country'] == 'ZAF'
    # Check Mitigation
    db_mitigation = TestSession.query(Mitigation).filter_by(submission_id=submission.id).first()
    assert db_mitigation is not None
    assert db_mitigation.sector is not None
    # Check Adaptaion
    db_adap = TestSession.query(Adaptaion).filter_by(submission_id=submission.id).first()
    assert db_adap is not None
    assert db_adap.sector is not None
