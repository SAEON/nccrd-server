"""
User management: a national admin manages roles on every site, a province
site's admin only on theirs, and nobody can hand out more than they have.
Roles on the national site count on every site. Reviewers and admins are
emailed when there's work waiting on their site.
"""
import pytest
from starlette.testclient import TestClient

import nccrd.api
import nccrd.api.lib.mail
from nccrd.api.lib.auth import create_access_token, hash_password
from nccrd.config import nccrd_config
from nccrd.db.models.rbac import Login, Permission, PermissionXrefRole, Role, Tenant, User, UserXrefRoleXrefTenant
from test import TestSession
from test.factories import FactorySession, MitigationFactory, SubmissionFactory

CONTRIBUTOR = ['create-submission', 'upload-template']
REVIEWER = CONTRIBUTOR + ['update-submission', 'validate-submission']
SITE_ADMIN = REVIEWER + ['delete-submission', 'assign-role', 'view-users', 'view-roles', 'view-tenants']
SYSADMIN = SITE_ADMIN + ['view-permissions', 'change-submission-owner']


@pytest.fixture
def sites():
    national = Tenant(hostname='test.nccrd.localhost', title='National', short_title='NCCRD', is_default=True,
                      include_unbounded_submissions=True)
    mccrd = Tenant(hostname='mccrd.example.org', title='Mpumalanga', short_title='MCCRD', slug='mccrd', province='Mpumalanga')
    gccrd = Tenant(hostname='gccrd.example.org', title='Gauteng', short_title='GCCRD', slug='gccrd', province='Gauteng')
    FactorySession.add_all([national, mccrd, gccrd])
    FactorySession.commit()
    return {'national': national, 'mccrd': mccrd, 'gccrd': gccrd}


@pytest.fixture
def roles():
    made = {}
    for name, permissions in [('contributor', CONTRIBUTOR), ('reviewer', REVIEWER), ('site-admin', SITE_ADMIN),
                              ('sysadmin', SYSADMIN)]:
        role = Role(name=name)
        FactorySession.add(role)
        FactorySession.flush()
        for permission_name in permissions:
            permission = FactorySession.query(Permission).filter_by(name=permission_name).first()
            if permission is None:
                permission = Permission(name=permission_name)
                FactorySession.add(permission)
                FactorySession.flush()
            FactorySession.add(PermissionXrefRole(permission_id=permission.id, role_id=role.id))
        made[name] = role
    FactorySession.commit()
    return made


def person(email, *grants, name=None):
    """A user holding ``grants`` ((role, site), ...), and a client signed in as them."""
    user = User(name=name or email.split('@')[0].title(), email=email, password_hash=hash_password('a-long-password'))
    FactorySession.add(user)
    FactorySession.flush()
    for role, site in grants:
        FactorySession.add(UserXrefRoleXrefTenant(user_id=user.id, role_id=role.id, tenant_id=site.id))
    FactorySession.commit()
    return user


def client(user, site=None):
    headers = {'Authorization': f'Bearer {create_access_token(user)}', 'Host': 'test.nccrd.localhost'}
    if site is not None and site.province:
        headers['X-NCCRD-Site-Province'] = site.province
    return TestClient(app=nccrd.api.app, headers=headers)


@pytest.fixture
def outbox(monkeypatch):
    sent = []
    monkeypatch.setattr(nccrd_config.NCCRD.MAIL, 'HOST', 'smtp.example.org')
    monkeypatch.setattr(nccrd_config.NCCRD.MAIL, 'FROM', 'ict@example.org')
    monkeypatch.setattr(nccrd_config.NCCRD, 'UI_URL', 'https://nccrd.example.org')
    monkeypatch.setattr(nccrd.api.lib.mail, '_deliver', sent.append)
    return sent


# ── Roles across sites ────────────────────────────────────────────────────────


def test_national_roles_count_on_every_site_and_province_roles_only_there(sites, roles):
    national_contributor = person('n@example.org', (roles['contributor'], sites['national']))
    mp_reviewer = person('m@example.org', (roles['reviewer'], sites['mccrd']))

    me = client(national_contributor, sites['mccrd']).get('/rbac/me').json()
    assert me['roles'] == ['contributor'] and 'create-submission' in me['permissions']

    assert 'validate-submission' in client(mp_reviewer, sites['mccrd']).get('/rbac/me').json()['permissions']
    assert client(mp_reviewer, sites['gccrd']).get('/rbac/me').json()['permissions'] == []
    assert client(mp_reviewer).get('/rbac/me').json()['permissions'] == []


# ── Who sees whom ─────────────────────────────────────────────────────────────


def test_national_admin_sees_everyone_with_their_roles_and_last_login(sites, roles):
    admin = person('admin@example.org', (roles['sysadmin'], sites['national']))
    thandi = person('thandi@example.org', (roles['reviewer'], sites['mccrd']), name='Thandi M')
    person('sipho@example.org', name='Sipho K')
    person('pending@example.org').registration_status = 'pending'
    FactorySession.commit()
    FactorySession.add(Login(user_id=thandi.id))
    FactorySession.commit()

    people = client(admin).get('/rbac/users').json()
    assert [p['email'] for p in people] == ['admin@example.org', 'sipho@example.org', 'thandi@example.org']
    by_email = {p['email']: p for p in people}
    assert [(r['role'], r['site']) for r in by_email['thandi@example.org']['roles']] == [('reviewer', 'MCCRD')]
    assert by_email['thandi@example.org']['last_login'] is not None
    assert by_email['sipho@example.org']['last_login'] is None

    assert [p['email'] for p in client(admin).get('/rbac/users', params={'q': 'THAN'}).json()] == ['thandi@example.org']


def test_province_admin_sees_their_site_and_finds_others_only_by_full_email(sites, roles):
    mp_admin = person('mp.admin@example.org', (roles['site-admin'], sites['mccrd']))
    person('mp.reviewer@example.org', (roles['reviewer'], sites['mccrd']), (roles['reviewer'], sites['gccrd']))
    person('gp.reviewer@example.org', (roles['reviewer'], sites['gccrd']))
    person('newcomer@example.org')
    mp = client(mp_admin, sites['mccrd'])

    people = mp.get('/rbac/users').json()
    assert {p['email'] for p in people} == {'mp.admin@example.org', 'mp.reviewer@example.org'}
    # Their roles on other sites aren't shown.
    reviewer = next(p for p in people if p['email'] == 'mp.reviewer@example.org')
    assert [r['site'] for r in reviewer['roles']] == ['MCCRD']

    assert mp.get('/rbac/users', params={'q': 'newcomer'}).json() == []
    assert [p['email'] for p in mp.get('/rbac/users', params={'q': 'Newcomer@example.org'}).json()] == ['newcomer@example.org']

    # Not an admin on Gauteng.
    assert client(mp_admin, sites['gccrd']).get('/rbac/users').status_code == 403


# ── Who may grant what ────────────────────────────────────────────────────────


def test_grant_options_follow_the_admins_own_roles(sites, roles):
    sysadmin = person('admin@example.org', (roles['sysadmin'], sites['national']))
    mp_admin = person('mp.admin@example.org', (roles['site-admin'], sites['mccrd']))

    everything = client(sysadmin).get('/rbac/grants').json()
    assert [s['name'] for s in everything['sites']] == ['NCCRD', 'GCCRD', 'MCCRD']  # national first
    assert {r['name'] for r in everything['roles']} == {'contributor', 'reviewer', 'site-admin', 'sysadmin'}

    theirs = client(mp_admin, sites['mccrd']).get('/rbac/grants').json()
    assert [s['name'] for s in theirs['sites']] == ['MCCRD']
    assert {r['name'] for r in theirs['roles']} == {'contributor', 'reviewer', 'site-admin'}


def test_province_admin_grants_and_takes_away_roles_on_their_site_only(sites, roles):
    mp_admin = person('mp.admin@example.org', (roles['site-admin'], sites['mccrd']))
    newcomer = person('newcomer@example.org')
    mp = client(mp_admin, sites['mccrd'])
    grant = f'/rbac/users/{newcomer.id}/roles'

    r = mp.post(grant, json={'role_id': roles['reviewer'].id, 'tenant_id': sites['mccrd'].id})
    assert r.status_code == 200, r.text
    assignment = r.json()['id']

    assert mp.post(grant, json={'role_id': roles['reviewer'].id, 'tenant_id': sites['gccrd'].id}).status_code == 403
    assert mp.post(grant, json={'role_id': roles['reviewer'].id, 'tenant_id': sites['national'].id}).status_code == 403
    r = mp.post(grant, json={'role_id': roles['sysadmin'].id, 'tenant_id': sites['mccrd'].id})
    assert r.status_code == 403
    assert 'permissions you have yourself' in r.json()['detail']

    assert mp.delete(f'{grant}/{assignment}').status_code == 200
    assert TestSession.query(UserXrefRoleXrefTenant).filter_by(user_id=newcomer.id).count() == 0


def test_nobody_takes_away_their_own_roles_or_roles_on_sites_they_dont_run(sites, roles):
    sysadmin = person('admin@example.org', (roles['sysadmin'], sites['national']))
    mp_admin = person('mp.admin@example.org', (roles['site-admin'], sites['mccrd']))
    gp_reviewer = person('gp@example.org', (roles['reviewer'], sites['gccrd']))
    own = TestSession.query(UserXrefRoleXrefTenant).filter_by(user_id=mp_admin.id).one().id
    theirs = TestSession.query(UserXrefRoleXrefTenant).filter_by(user_id=gp_reviewer.id).one().id
    national = TestSession.query(UserXrefRoleXrefTenant).filter_by(user_id=sysadmin.id).one().id
    mp = client(mp_admin, sites['mccrd'])

    assert mp.delete(f'/rbac/users/{mp_admin.id}/roles/{own}').status_code == 403
    assert mp.delete(f'/rbac/users/{gp_reviewer.id}/roles/{theirs}').status_code == 403
    assert mp.delete(f'/rbac/users/{sysadmin.id}/roles/{national}').status_code == 403
    # The national admin can.
    assert client(sysadmin).delete(f'/rbac/users/{mp_admin.id}/roles/{own}').status_code == 200


def test_approving_a_request_gives_only_a_role_the_admin_may_grant(sites, roles):
    mp_admin = person('mp.admin@example.org', (roles['site-admin'], sites['mccrd']))
    request = person('new@example.org')
    request.registration_status = 'pending'
    request.registration_tenant_id = sites['mccrd'].id
    FactorySession.commit()
    mp = client(mp_admin, sites['mccrd'])

    assert mp.post(f'/rbac/registrations/{request.id}/approve', json={'role_id': roles['sysadmin'].id}).status_code == 403
    assert mp.post(f'/rbac/registrations/{request.id}/approve', json={'role_id': roles['contributor'].id}).status_code == 200


def test_each_site_sees_its_own_account_requests(sites, roles, api):
    sysadmin = person('admin@example.org', (roles['sysadmin'], sites['national']))
    mp_admin = person('mp.admin@example.org', (roles['site-admin'], sites['mccrd']))
    form = {'organisation': 'City', 'password': 'a-long-password', 'accept_privacy_notice': True}
    anonymous = TestClient(app=nccrd.api.app, headers={'Host': 'test.nccrd.localhost'})
    anonymous.post('/auth/register', json={'name': 'On MP', 'email': 'mp@example.org', **form},
                   headers={'X-NCCRD-Site-Province': 'mpumalanga'})
    anonymous.post('/auth/register', json={'name': 'On GP', 'email': 'gp@example.org', **form},
                   headers={'X-NCCRD-Site-Province': 'gauteng'})

    assert [r['email'] for r in client(mp_admin, sites['mccrd']).get('/rbac/registrations').json()] == ['mp@example.org']
    assert {r['email'] for r in client(sysadmin).get('/rbac/registrations').json()} == {'mp@example.org', 'gp@example.org'}
    gp_request = TestSession.query(User).filter_by(email='gp@example.org').one().id
    r = client(mp_admin, sites['mccrd']).post(f'/rbac/registrations/{gp_request}/reject')
    assert r.status_code == 404


def test_logins_are_recorded(sites, roles):
    user = person('thandi@example.org')
    anonymous = TestClient(app=nccrd.api.app, headers={'Host': 'test.nccrd.localhost'})
    assert anonymous.post('/auth/login', json={'email': 'thandi@example.org', 'password': 'wrong-password'}).status_code == 401
    assert anonymous.post('/auth/login', json={'email': 'thandi@example.org', 'password': 'a-long-password'}).status_code == 200
    assert TestSession.query(Login).filter_by(user_id=user.id).count() == 1


# ── Alerts ────────────────────────────────────────────────────────────────────


def test_request_alert_goes_to_the_sites_admins_else_the_national_ones(sites, roles, outbox):
    person('admin@example.org', (roles['sysadmin'], sites['national']))
    person('gp.admin@example.org', (roles['site-admin'], sites['gccrd']))
    form = {'organisation': 'City', 'password': 'a-long-password', 'accept_privacy_notice': True}
    anonymous = TestClient(app=nccrd.api.app, headers={'Host': 'test.nccrd.localhost'})

    anonymous.post('/auth/register', json={'name': 'On GP', 'email': 'gp@example.org', **form},
                   headers={'X-NCCRD-Site-Province': 'gauteng'})
    anonymous.post('/auth/register', json={'name': 'On MP', 'email': 'mp@example.org', **form},
                   headers={'X-NCCRD-Site-Province': 'mpumalanga'})

    assert [(m['To'], m['Subject']) for m in outbox] == [
        ('gp.admin@example.org', 'New account request on GCCRD'),
        ('admin@example.org', 'New account request on MCCRD'),  # Mpumalanga has no admin of its own
    ]
    assert 'https://nccrd.example.org/gauteng/admin/registrations' in outbox[0].get_content()


def test_changed_project_alerts_the_provinces_reviewers_not_the_submitter(sites, roles, outbox):
    person('national.reviewer@example.org', (roles['reviewer'], sites['national']))
    person('mp.reviewer@example.org', (roles['reviewer'], sites['mccrd']))
    owner = person('owner@example.org', (roles['contributor'], sites['national']))
    project = SubmissionFactory(title='Solar pumps', createdby=owner.id, geo_location={'province': 'Mpumalanga'},
                                data_source='react_app', intervention_measurement='Mitigation')
    MitigationFactory(submission_id=project.id)

    r = client(owner).patch(f'/submission/update_new_submission/{project.id}', json={'title': 'Solar pumps 2'})
    assert r.status_code == 200, r.text

    [message] = outbox
    assert (message['To'], message['Subject']) == ('mp.reviewer@example.org', 'A project is waiting for review on MCCRD')
    assert 'The project "Solar pumps 2" was changed' in message.get_content()
    assert 'https://nccrd.example.org/mpumalanga/review' in message.get_content()


def test_project_outside_reviewed_provinces_alerts_the_national_reviewers(sites, roles, outbox):
    person('national.reviewer@example.org', (roles['reviewer'], sites['national']))
    person('mp.reviewer@example.org', (roles['reviewer'], sites['mccrd']))
    owner = person('owner@example.org', (roles['contributor'], sites['national']))
    project = SubmissionFactory(title='Dams', createdby=owner.id, geo_location={'province': 'Gauteng'},
                                data_source='react_app', intervention_measurement='Mitigation')
    MitigationFactory(submission_id=project.id)

    assert client(owner).patch(f'/submission/update_new_submission/{project.id}', json={'title': 'Dams'}).status_code == 200
    assert [(m['To'], m['Subject']) for m in outbox] == [
        ('national.reviewer@example.org', 'A project is waiting for review on NCCRD'),
    ]
