"""
POPIA: personal information is collected with consent and shown only to
those who need it. Signing up needs the privacy notice accepted; a project
manager's contact details need the submitter's confirmation that the manager
agreed; and their email and phone number are for the project's owner and
reviewers, not the public.
"""
import pytest

from nccrd.db.models import Submission
from nccrd.db.models.rbac import Role, Tenant, User
from test import TestSession
from test.factories import FactorySession, SubmissionFactory

CONTACT = {'project_manager_name': 'A Manager', 'project_manager_email': 'manager@example.org',
           'project_manager_contact_number': '082 123 4567'}
NEW_PROJECT = {'title': 'Solar for clinics', 'intervention_measurement': 'Mitigation',
               'implementation_organization': 'DFFE', 'mitigation_data': {'sector': 'Energy'},
               'geo_location': {'country': 'ZAF', 'province': 'Gauteng'}, **CONTACT}


@pytest.fixture(autouse=True)
def tenant():
    FactorySession.add(Tenant(hostname='test.nccrd.localhost', title='Test', is_default=True,
                              include_unbounded_submissions=True))
    FactorySession.add(Role(name='user'))
    FactorySession.commit()


def test_signing_up_needs_the_privacy_notice_accepted(api):
    request = {'name': 'Thandi M', 'email': 'thandi@example.org', 'organisation': 'City of Joburg',
               'password': 'a-long-password'}
    client = api()

    r = client.post('/auth/register', json=request, headers={'Authorization': ''})
    assert r.status_code == 422 and 'privacy notice' in r.json()['detail']
    assert TestSession.query(User).filter_by(email='thandi@example.org').count() == 0

    r = client.post('/auth/register', json={**request, 'accept_privacy_notice': True}, headers={'Authorization': ''})
    assert r.status_code == 202, r.text
    assert TestSession.query(User).filter_by(email='thandi@example.org').one().privacy_notice_accepted_at


def test_a_project_manager_contact_needs_the_submitters_confirmation(api):
    client = api(permissions=['create-submission'])

    r = client.post('/submission/new_submission', json=NEW_PROJECT)
    assert r.status_code == 422 and 'project manager agreed' in r.json()['detail']

    r = client.post('/submission/new_submission', json={**NEW_PROJECT, 'contact_consent': True})
    assert r.status_code in (200, 201), r.text
    assert TestSession.query(Submission).one().contact_consent_at


def test_a_changed_contact_needs_confirming_again(api):
    owner = api(permissions=['create-submission'])
    project = SubmissionFactory(createdby=_user_id(owner), **CONTACT)
    edit = f'/submission/update_new_submission/{project.id}'

    assert owner.patch(edit, json={'title': 'Renamed', **CONTACT}).status_code == 200       # same contact
    r = owner.patch(edit, json={'project_manager_email': 'someone.else@example.org'})
    assert r.status_code == 422 and 'project manager agreed' in r.json()['detail']
    r = owner.patch(edit, json={'project_manager_email': 'someone.else@example.org', 'contact_consent': True})
    assert r.status_code == 200, r.text
    assert TestSession.query(Submission).filter_by(id=project.id).one().contact_consent_at


def test_contact_details_are_for_the_owner_and_reviewers_only(api):
    owner = api(email='owner@example.org')
    project = SubmissionFactory(createdby=_user_id(owner), **CONTACT)
    page = f'/submission/read_submission/{project.id}'

    public = api(email='someone@example.org').get(page).json()
    assert public['project_manager_name'] == 'A Manager'
    assert public['project_manager_email'] is None and public['project_manager_contact_number'] is None

    for client in (owner, api(email='reviewer@example.org', permissions=['validate-submission'])):
        shown = client.get(page).json()
        assert shown['project_manager_email'] == 'manager@example.org'
        assert shown['project_manager_contact_number'] == '082 123 4567'

    listed = owner.get('/submission/list_submission').json()
    assert listed and 'project_manager_email' not in listed[0] and 'project_manager_contact_number' not in listed[0]


def _user_id(client):
    import jwt
    return int(jwt.decode(client.headers['Authorization'].split()[1], options={'verify_signature': False})['sub'])
