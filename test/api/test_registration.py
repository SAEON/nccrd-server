"""
Self sign-up: anyone can request an account, it can't be used until an admin
approves it with a role, and the form never reveals which emails exist.
"""
import pytest

from nccrd.db.models.rbac import Role, Tenant, User, UserXrefRoleXrefTenant
from test import TestSession
from test.factories import FactorySession

REQUEST = {'name': 'Thandi M', 'email': 'Thandi.M@example.org', 'organisation': 'City of Joburg',
           'password': 'a-long-password', 'note': 'I capture the city’s adaptation projects.'}


@pytest.fixture
def admin(api):
    FactorySession.add(Tenant(hostname='test.nccrd.localhost', title='Test', is_default=True))
    FactorySession.add(Role(name='user'))
    FactorySession.commit()
    return api(email='admin@example.org', permissions=['assign-role'])


def _login(client, email='thandi.m@example.org', password='a-long-password'):
    return client.post('/auth/login', json={'email': email, 'password': password}, headers={'Authorization': ''})


def test_request_waits_for_approval_then_logs_in(admin):
    r = admin.post('/auth/register', json=REQUEST, headers={'Authorization': ''})
    assert r.status_code == 202

    blocked = _login(admin)
    assert blocked.status_code == 403 and 'waiting' in blocked.json()['detail']
    assert _login(admin, password='wrong-password').status_code == 401     # no hint without the password

    queue = admin.get('/rbac/registrations').json()
    assert [(q['email'], q['organisation']) for q in queue] == [('Thandi.M@example.org', 'City of Joburg')]

    role = TestSession.query(Role).filter_by(name='user').one()
    approved = admin.post(f"/rbac/registrations/{queue[0]['id']}/approve", json={'role_id': role.id})
    assert approved.status_code == 200 and approved.json()['registration_status'] == 'approved'
    assert TestSession.query(UserXrefRoleXrefTenant).filter_by(user_id=queue[0]['id'], role_id=role.id).count() == 1

    assert _login(admin).status_code == 200                                # email case doesn't matter
    assert admin.get('/rbac/registrations').json() == []


def test_rejected_request_cannot_log_in(admin):
    admin.post('/auth/register', json=REQUEST, headers={'Authorization': ''})
    user_id = admin.get('/rbac/registrations').json()[0]['id']
    assert admin.post(f'/rbac/registrations/{user_id}/reject').json()['registration_status'] == 'rejected'
    assert _login(admin).status_code == 403
    assert admin.post(f'/rbac/registrations/{user_id}/approve', json={'role_id': 1}).status_code == 404


def test_existing_email_gets_the_same_reply_and_no_new_account(admin):
    first = admin.post('/auth/register', json={**REQUEST, 'email': 'ADMIN@example.org'}, headers={'Authorization': ''})
    assert first.status_code == 202
    assert TestSession.query(User).filter(User.email.ilike('admin@example.org')).count() == 1


def test_short_password_and_non_admin_are_refused(api, admin):
    assert admin.post('/auth/register', json={**REQUEST, 'password': 'short'}, headers={'Authorization': ''}).status_code == 422
    capturer = api(email='capturer@example.org', permissions=['create-submission'])
    assert capturer.get('/rbac/registrations').status_code == 403
