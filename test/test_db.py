import uuid
from datetime import datetime

from nccrd.db.models import Submission, Mitigation, Adaptation
from test import TestSession
from .factories import (
    SubmissionFactory,
    MitigationFactory,
    AdaptationFactory,
)

# Note: *Factory() calls already commit via FactorySession (sqlalchemy_session_persistence
# = 'commit'), so their results must not be re-added to TestSession — a second session
# can't attach an object that's already attached elsewhere. TestSession is used purely to
# read back what the factory wrote, via a separate session/connection.


def test_submission():
    submission = SubmissionFactory()
    result = TestSession.query(Submission).filter_by(id=submission.id).first()
    assert result is not None
    assert result.title == submission.title
    assert result.description == submission.description


def test_mitigation():
    submission = SubmissionFactory()
    mitigation = MitigationFactory(submission_id=submission.id)
    result = TestSession.query(Mitigation).filter_by(id=mitigation.id).first()
    assert result is not None
    assert result.sector == mitigation.sector
    assert result.project_type == mitigation.project_type


def test_adaptation():
    submission = SubmissionFactory()
    adaptation = AdaptationFactory(submission_id=submission.id)
    result = TestSession.query(Adaptation).filter_by(id=adaptation.id).first()
    assert result is not None
    assert result.sector == adaptation.sector
    assert result.hazard == adaptation.hazard


def test_submission_all_fields():
    submission = Submission(
        id=uuid.uuid4(),
        title='Test Submission',
        intervention_measurement='Mitigation',
        description='A test submission for all fields.',
        implementation_status='Completed',
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
            'coordinates': [30.374, -27.9363],
        },
        project_manager_name='Manager',
        project_manager_organization='Manager Org',
        project_manager_email='manager@example.com',
        project_manager_contact_number='1234567890',
        submission_status='Pending',
        submission_comments='No comments',
        issubmitted=True,
        research='Research details',
        platform='WEB',
        createdby=None,
        createdate=datetime(2025, 6, 23),
        updatedate=datetime(2025, 6, 23),
        updatedby=None,
        deletedby=None,
        deletedate=None,
        deleted=False,
    )
    TestSession.add(submission)
    TestSession.commit()

    mitigation = MitigationFactory(submission_id=submission.id)
    adaptation = AdaptationFactory(submission_id=submission.id)

    db_submission = TestSession.query(Submission).filter_by(id=submission.id).first()
    assert db_submission is not None
    assert db_submission.title == 'Test Submission'
    assert db_submission.implementation_organization == 'Test Org'
    assert db_submission.funding_amount == 12345.67
    assert db_submission.geo_location['country'] == 'ZAF'

    db_mitigation = TestSession.query(Mitigation).filter_by(submission_id=submission.id).first()
    assert db_mitigation is not None
    assert db_mitigation.sector is not None

    db_adaptation = TestSession.query(Adaptation).filter_by(submission_id=submission.id).first()
    assert db_adaptation is not None
    assert db_adaptation.sector is not None


def test_submission_required_fields():
    submission = SubmissionFactory()
    db_submission = TestSession.query(Submission).filter_by(id=submission.id).first()
    assert db_submission is not None
    assert db_submission.id == submission.id
    assert db_submission.title == submission.title


def test_submission_update():
    submission = SubmissionFactory()
    db_submission = TestSession.query(Submission).filter_by(id=submission.id).first()
    db_submission.title = "Updated Title"
    TestSession.commit()
    TestSession.expire_all()
    db_submission = TestSession.query(Submission).filter_by(id=submission.id).first()
    assert db_submission.title == "Updated Title"


def test_submission_delete():
    submission = SubmissionFactory()
    db_submission = TestSession.query(Submission).filter_by(id=submission.id).first()
    TestSession.delete(db_submission)
    TestSession.commit()
    db_submission = TestSession.query(Submission).filter_by(id=submission.id).first()
    assert db_submission is None


def test_mitigation_submission_relationship():
    submission = SubmissionFactory()
    mitigation = MitigationFactory(submission_id=submission.id)
    db_mitigation = TestSession.query(Mitigation).filter_by(id=mitigation.id).first()
    assert db_mitigation.submission_id == submission.id


def test_adaptation_submission_relationship():
    submission = SubmissionFactory()
    adaptation = AdaptationFactory(submission_id=submission.id)
    db_adaptation = TestSession.query(Adaptation).filter_by(id=adaptation.id).first()
    assert db_adaptation.submission_id == submission.id


def test_submission_geo_location_format():
    submission = SubmissionFactory(geo_location={'country': 'ZAF', 'type': 'Point', 'coordinates': [0, 0]})
    db_submission = TestSession.query(Submission).filter_by(id=submission.id).first()
    assert isinstance(db_submission.geo_location, dict)
    assert 'country' in db_submission.geo_location
