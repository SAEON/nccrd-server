"""
Visitor numbers: public page views are counted per site and day, with
nothing that identifies a visitor; admins with view-stats see them.
"""
from datetime import datetime, timedelta

import pytest
from starlette.testclient import TestClient

import nccrd.api
from nccrd.api.routers.stats import counted_path
from nccrd.db.models.rbac import DownloadLog, Login, PageView, Permission, PermissionXrefRole, Role, Tenant
from test import TestSession
from test.api.test_user_management import client, person
from test.factories import FactorySession, SubmissionFactory

PROJECT = '0f1e2d3c-4b5a-4968-8776-655443322110'


@pytest.fixture
def sites():
    national = Tenant(hostname='test.nccrd.localhost', title='National', short_title='NCCRD', is_default=True,
                      include_unbounded_submissions=True)
    mccrd = Tenant(hostname='mccrd.example.org', title='Mpumalanga', short_title='MCCRD', slug='mccrd', province='Mpumalanga')
    FactorySession.add_all([national, mccrd])
    FactorySession.commit()
    return {'national': national, 'mccrd': mccrd}


@pytest.fixture
def stats_role():
    role = Role(name='site-admin')
    permission = Permission(name='view-stats')
    FactorySession.add_all([role, permission])
    FactorySession.flush()
    FactorySession.add(PermissionXrefRole(permission_id=permission.id, role_id=role.id))
    FactorySession.commit()
    return role


def visitor(site=None):
    headers = {'Host': 'test.nccrd.localhost'}
    if site is not None and site.province:
        headers['X-NCCRD-Site-Province'] = site.province
    return TestClient(app=nccrd.api.app, headers=headers)


@pytest.mark.parametrize('path, counted', [
    ('/', '/'), ('/reports', '/reports'), ('/reports/', '/reports'), ('/About?x=1#top', '/about'),
    (f'/submission/{PROJECT}', f'/submission/{PROJECT}'),
    ('/admin/users', None), ('/review', None), ('/reset-password', None), ('/submission/new', None),
    ('/submission/edit/' + PROJECT, None), ('/anything-else', None),
])
def test_only_public_pages_are_counted(path, counted):
    assert counted_path(path) == counted


def test_views_are_counted_per_site_page_and_day(sites):
    for _ in range(3):
        assert visitor().post('/stats/view', json={'path': '/reports'}).status_code == 204
    visitor(sites['mccrd']).post('/stats/view', json={'path': '/reports'})
    visitor().post('/stats/view', json={'path': '/admin/users'})

    rows = {(r.tenant_id, r.path): r.views for r in TestSession.query(PageView)}
    assert rows == {(sites['national'].id, '/reports'): 3, (sites['mccrd'].id, '/reports'): 1}


def test_admins_see_their_sites_numbers(sites, stats_role):
    project = SubmissionFactory(title='Solar pumps')
    mp = visitor(sites['mccrd'])
    for path in ['/', '/', '/reports', f'/submission/{project.id}', f'/submission/{project.id}']:
        mp.post('/stats/view', json={'path': path})
    visitor().post('/stats/view', json={'path': '/'})
    FactorySession.add_all([DownloadLog(tenant_id=sites['mccrd'].id, submission_ids=[]),
                            DownloadLog(tenant_id=sites['national'].id, submission_ids=[])])
    someone = person('someone@example.org')
    FactorySession.add_all([Login(user_id=someone.id), Login(user_id=someone.id),
                            Login(user_id=someone.id, timestamp=datetime.utcnow() - timedelta(days=60))])
    FactorySession.commit()

    mp_admin = person('mp.admin@example.org', (stats_role, sites['mccrd']))
    r = client(mp_admin, sites['mccrd']).get('/stats', params={'days': 7})
    assert r.status_code == 200, r.text
    stats = r.json()
    assert (stats['views'], stats['downloads'], stats['people_logged_in']) == (5, 1, 1)
    assert len(stats['days']) == 7 and stats['days'][-1]['views'] == 5 and stats['days'][-1]['downloads'] == 1
    assert [(p['name'], p['views']) for p in stats['pages']] == [('Home (project search)', 2), ('Data reports', 1)]
    assert [(p['name'], p['views']) for p in stats['projects']] == [('Solar pumps', 2)]
    assert stats['sites'] == []  # only the national site compares sites

    national_admin = person('admin@example.org', (stats_role, sites['national']))
    national = client(national_admin).get('/stats').json()
    assert national['views'] == 1
    assert [(s['name'], s['views']) for s in national['sites']] == [('MCCRD', 5), ('NCCRD', 1)]


def test_numbers_are_for_admins_only(sites, stats_role):
    assert visitor().get('/stats').status_code == 401
    assert client(person('nobody@example.org')).get('/stats').status_code == 403
    mp_admin = person('mp.admin@example.org', (stats_role, sites['mccrd']))
    assert client(mp_admin).get('/stats').status_code == 403  # not on the national site


def test_downloads_record_their_site(sites, api):
    SubmissionFactory()
    r = visitor(sites['mccrd']).get('/report/export', params={'format': 'csv'})
    assert r.status_code == 200, r.text
    assert [d.tenant_id for d in TestSession.query(DownloadLog)] == [sites['mccrd'].id]
