"""
Province sites: one API serves the national NCCRD and province sites such as
the MCCRD. The web interface names its site in the X-NCCRD-Site header (it
may call the API on another host); a province site lists the projects
located in its province and those submitted on it, with its own branding.
"""
import csv
import io

import pytest

import nccrd.db
from nccrd.api.routers.submission import _link_submission_to_tenant
from nccrd.db.models.rbac import Tenant, TenantXrefSubmission
from test.factories import FactorySession, SubmissionFactory


@pytest.fixture
def sites():
    national = Tenant(
        hostname='test.nccrd.localhost', title='National Climate Change Response Database',
        is_default=True, include_unbounded_submissions=True,
    )
    mpumalanga = Tenant(
        hostname='mccrd.environment.gov.za', slug='mccrd', title='Mpumalanga Climate Change Response Database',
        short_title='MCCRD', province='Mpumalanga', logo_url='/sites/mccrd/logo.jpg',
        theme={'accent-primary': '#622700'}, front_matter={'about': {'title': 'Welcome', 'content': 'Text'}},
        hero_image={'url': '/sites/mccrd/hero.jpg', 'credit': 'Dietmar Rabich', 'license': 'CC BY-SA 4.0'},
    )
    FactorySession.add_all([national, mpumalanga])
    FactorySession.commit()
    return national, mpumalanga


def _titles(client, site=None):
    headers = {'X-NCCRD-Site': site} if site else {}
    r = client.get('/submission/list_submission', headers=headers)
    assert r.status_code == 200, r.text
    return {s['title'] for s in r.json()}


@pytest.mark.parametrize('site, short_title', [
    (None, None),                            # the request's Host: the default site
    ('mccrd.localhost', 'MCCRD'),            # local development, by slug
    ('mccrd.environment.gov.za', 'MCCRD'),   # production, by hostname
    ('MCCRD.localhost:5173', 'MCCRD'),
    ('unknown.example.org', None),           # unknown: the default site
    ('mccrd', None),                         # a bare word is not a site address
])
def test_site_is_resolved_from_header(api, sites, site, short_title):
    r = api().get('/site', headers={'X-NCCRD-Site': site} if site else {})
    assert r.status_code == 200, r.text
    assert r.json()['short_title'] == short_title


def test_site_returns_branding_publicly(api, sites):
    from starlette.testclient import TestClient
    import nccrd.api

    r = TestClient(nccrd.api.app).get('/site', headers={'X-NCCRD-Site': 'mccrd.localhost'})
    assert r.status_code == 200, r.text
    site = r.json()
    assert site['title'] == 'Mpumalanga Climate Change Response Database'
    assert site['province'] == 'Mpumalanga'
    assert site['logo_url'] == '/sites/mccrd/logo.jpg'
    assert site['theme'] == {'accent-primary': '#622700'}
    assert site['front_matter']['about']['title'] == 'Welcome'
    assert site['hero_image']['credit'] == 'Dietmar Rabich'
    assert 'id' not in site and 'include_unbounded_submissions' not in site


def test_province_site_lists_its_province_and_its_own_projects(api, sites):
    national, mpumalanga = sites
    SubmissionFactory(title='string', geo_location={'province': 'Mpumalanga'})
    SubmissionFactory(title='shared', geo_location={'province': [{'term': 'Limpopo'}, {'term': 'Mpumalanga'}]})
    SubmissionFactory(title='gauteng', geo_location={'province': 'Gauteng'})
    SubmissionFactory(title='nowhere')
    linked = SubmissionFactory(title='submitted there', geo_location={'province': 'Gauteng'})
    FactorySession.add(TenantXrefSubmission(tenant_id=mpumalanga.id, submission_id=linked.id))
    FactorySession.commit()

    client = api()
    assert _titles(client, 'mccrd.localhost') == {'string', 'shared', 'submitted there'}
    assert _titles(client) == {'string', 'shared', 'gauteng', 'nowhere'}


def test_province_site_scopes_reports(api, sites):
    SubmissionFactory(title='mp', geo_location={'province': 'Mpumalanga'})
    SubmissionFactory(title='gp', geo_location={'province': 'Gauteng'})
    client = api()

    r = client.get('/report/summary', headers={'X-NCCRD-Site': 'mccrd.localhost'})
    assert r.status_code == 200, r.text
    assert r.json()['total'] == 1

    # A download link names the site as a query parameter.
    r = client.get('/report/export', params={'format': 'csv', 'site': 'mccrd.localhost'})
    assert r.status_code == 200, r.text
    assert [row['Title'] for row in csv.DictReader(io.StringIO(r.text.lstrip('\ufeff')))] == ['mp']


def test_submission_on_province_site_is_also_national(sites):
    national, mpumalanga = sites
    submission = SubmissionFactory(title='new')
    db = nccrd.db.Session()
    _link_submission_to_tenant(db, submission.id, db.get(Tenant, mpumalanga.id))
    db.commit()

    linked = {x.tenant_id for x in db.query(TenantXrefSubmission).filter_by(submission_id=submission.id)}
    assert linked == {national.id, mpumalanga.id}


def test_province_site_offers_only_its_own_filter_options(api, sites):
    SubmissionFactory(geo_location={'province': 'Mpumalanga'}, implementation_status='Planned', funding_type='Grant')
    SubmissionFactory(geo_location={'province': 'Gauteng'}, implementation_status='Completed', funding_type='Loan')
    client = api()

    mpumalanga = client.get('/submission/facets/submission', headers={'X-NCCRD-Site': 'mccrd.localhost'}).json()
    assert mpumalanga['implementation_status'] == ['Planned']
    assert mpumalanga['funding_type'] == ['Grant']

    national = client.get('/submission/facets/submission').json()
    assert national['implementation_status'] == ['Completed', 'Planned']
