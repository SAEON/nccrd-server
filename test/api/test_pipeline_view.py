"""
The curators' read-only view of the data pipeline (/pipeline). The pipeline's
schemas aren't part of the app's migrations, so the populated case builds the
few tables it reads by hand.
"""
import pytest
from sqlalchemy import text

from nccrd.db.models.rbac import Tenant
from test import TestSession
from test.factories import FactorySession, SubmissionFactory

GP = "gauteng_register_2024"

_SCHEMA = """
CREATE SCHEMA pipeline;
CREATE SCHEMA silver;
CREATE TABLE pipeline.load_batch (id serial PRIMARY KEY, source text, file_name text,
                                  loaded_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE pipeline.curation (data_source text, source_key text, action text, reason text);
CREATE TABLE pipeline.sync_state (data_source text, source_key text, gold_id uuid);
CREATE TABLE pipeline.run (id serial PRIMARY KEY, kind text, applied boolean, summary jsonb,
                           ran_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE silver.submission (data_source text, source_key text);
CREATE TABLE silver.dq_issue (data_source text, source_key text, field text, issue text, value text);
CREATE TABLE silver.sync_conflict (data_source text, source_key text, gold_id uuid, reason text, fields jsonb);
"""


@pytest.fixture
def tenant():
    t = Tenant(hostname='test.nccrd.localhost', title='Test', is_default=True, include_unbounded_submissions=True)
    FactorySession.add(t)
    FactorySession.commit()
    return t


@pytest.fixture
def curator(api, tenant):
    return api(email='curator@example.org', permissions=['validate-submission'])


@pytest.fixture
def pipeline():
    """Three Gauteng source rows: two projects in the app (one public), one excluded,
    plus a deleted project that still has an issue (it must not count)."""
    public = SubmissionFactory(title='Solar clinic', data_source=GP)
    draft = SubmissionFactory(title='Bus lanes', data_source=GP, issubmitted=False, submission_status=None)
    gone = SubmissionFactory(title='Removed', data_source=GP, deleted=True)
    TestSession.execute(text(_SCHEMA))
    TestSession.execute(text(f"""
        INSERT INTO pipeline.load_batch (source, file_name) VALUES ('gauteng', 'register.xlsm');
        INSERT INTO pipeline.run (kind, applied, summary) VALUES ('gold', true, '{{"actions": {{"update": 2}}}}');
        INSERT INTO silver.submission VALUES ('{GP}', 'a'), ('{GP}', 'b'), ('{GP}', 'c'), ('{GP}', 'd');
        INSERT INTO pipeline.curation VALUES ('{GP}', 'c', 'exclude', 'junk');
        INSERT INTO pipeline.sync_state VALUES ('{GP}', 'a', '{public.id}'), ('{GP}', 'b', '{draft.id}'),
                                               ('{GP}', 'd', '{gone.id}');
        INSERT INTO silver.dq_issue VALUES ('{GP}', 'a', 'geo_location.province', 'no province', NULL),
                                           ('{GP}', 'b', 'geo_location.province', 'no province', NULL),
                                           ('{GP}', 'd', 'geo_location.province', 'no province', NULL),
                                           ('{GP}', 'b', 'estimated_budget_cost', 'budget not in a recognised form', 'R?');
        INSERT INTO silver.sync_conflict VALUES ('{GP}', 'a', '{public.id}', 'changed in the app since the last sync',
                                                 '["title"]'),
                                                ('{GP}', 'c', '{draft.id}', 'deleted in the app', '["deleted"]');
    """))
    TestSession.commit()
    yield {'public': public, 'draft': draft}
    TestSession.execute(text("DROP SCHEMA pipeline CASCADE; DROP SCHEMA silver CASCADE"))
    TestSession.commit()


def test_curators_only(api, tenant):
    assert api(email='visitor@example.org').get('/pipeline/status').status_code == 403


def test_a_database_without_the_pipeline(curator):
    r = curator.get('/pipeline/status')
    assert r.status_code == 200, r.text
    assert r.json() == {'available': False}
    assert curator.get('/pipeline/issues', params={'data_source': GP, 'field': 'x', 'issue': 'y'}).json() == \
        {'total': 0, 'projects': []}


def test_status(curator, pipeline):
    body = curator.get('/pipeline/status').json()
    assert body['available'] is True
    assert [(l['source'], l['file_name']) for l in body['loads']] == [('gauteng', 'register.xlsm')]
    assert body['sources'] == [{'data_source': GP, 'in_source': 4, 'excluded': 1, 'in_app': 2, 'public': 1}]
    assert body['runs'][0]['kind'] == 'gold' and body['runs'][0]['summary'] == {'actions': {'update': 2}}
    # Only the live conflict: row 'c' has since been excluded by curation.
    assert [(c['title'], c['fields']) for c in body['conflicts']] == [('Solar clinic', ['title'])]
    # The deleted project's issue doesn't count.
    assert {(i['field'], i['projects']) for i in body['issues']} == {
        ('geo_location.province', 2), ('estimated_budget_cost', 1)}


def test_issue_worklist(curator, pipeline):
    r = curator.get('/pipeline/issues', params={'data_source': GP, 'field': 'geo_location.province',
                                               'issue': 'no province'})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body['total'] == 2
    assert [(p['title'], p['public']) for p in body['projects']] == [('Bus lanes', False), ('Solar clinic', True)]
    assert {p['id'] for p in body['projects']} == {str(pipeline['public'].id), str(pipeline['draft'].id)}
