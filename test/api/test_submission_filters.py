"""
The Home page builds its filter dropdowns from GET /submission/facets/submission
and sends the chosen option back to GET /submission/list_submission. These tests
pin the contract that every facet option round-trips, across the legacy storage
shapes still present in production data.
"""
import csv
import io

import pytest

from nccrd.api.routers.submission import _vocab_terms
from nccrd.db.models.rbac import Tenant
from test.factories import AdaptationFactory, FactorySession, MitigationFactory, SubmissionFactory

HAZARD_REPR = (
    "[{'__typename': 'ControlledVocabulary', 'id': 'Drought', 'term': 'Drought', "
    "'tree': 'hazards', 'root': 'Hazard'}, {'__typename': 'ControlledVocabulary', "
    "'id': 'fa904137018d3f46eea2536429fe7f636938ba9c', 'term': 'Floods', 'tree': 'hazards', "
    "'root': 'Hazard'}]"
)


@pytest.mark.parametrize('value, expected', [
    (None, []),
    ('', []),
    ('[]', []),
    ('Gauteng', ['Gauteng']),
    ('Waste Recycling ', ['Waste Recycling']),
    ([{'term': 'Free State'}, {'term': 'Gauteng'}], ['Free State', 'Gauteng']),
    (HAZARD_REPR, ['Drought', 'Floods']),
    ('e455c5430615ba86bae602db94fecc441539e8e5', []),
    ('[{not a literal', ['[{not a literal']),
])
def test_vocab_terms(value, expected):
    assert _vocab_terms(value) == expected


@pytest.fixture
def client(api):
    FactorySession.add(Tenant(
        hostname='test.nccrd.localhost', title='Test Tenant',
        is_default=True, include_unbounded_submissions=True,
    ))
    FactorySession.commit()
    return api()


def _titles(client, **params):
    r = client.get('/submission/list_submission', params=params)
    assert r.status_code == 200, r.text
    return {s['title'] for s in r.json()}


def test_province_matches_string_and_term_list(client):
    SubmissionFactory(title='string', geo_location={'province': 'Free State'})
    SubmissionFactory(title='list', geo_location={'province': [{'id': 'Free State', 'term': 'Free State'}]})
    SubmissionFactory(title='other', geo_location={'province': 'Gauteng'})

    assert _titles(client, province='Free State') == {'string', 'list'}
    assert client.get('/submission/facets/submission').json()['province'] == ['Free State', 'Gauteng']


def test_hazard_matches_repr_list(client):
    s = SubmissionFactory(title='repr', intervention_measurement='Adaptation')
    AdaptationFactory(submission_id=s.id, hazard=HAZARD_REPR)

    assert client.get('/submission/facets/submission').json()['adaptation_hazard'] == ['Drought', 'Floods']
    assert _titles(client, adaptation_hazard='Floods') == {'repr'}
    assert _titles(client, adaptation_hazard='Flood') == set()


def test_trailing_whitespace_value_round_trips(client):
    s = SubmissionFactory(title='padded', intervention_measurement='Mitigation')
    MitigationFactory(submission_id=s.id, project_type='Waste Recycling ')

    assert 'Waste Recycling' in client.get('/submission/facets/submission').json()['mitigation_project_type']
    assert _titles(client, mitigation_project_type='Waste Recycling') == {'padded'}


def test_facets_exclude_deleted_submissions(client):
    s = SubmissionFactory(deleted=True, intervention_measurement='Mitigation')
    MitigationFactory(submission_id=s.id, sector='Energy Industries')

    assert 'Energy Industries' not in client.get('/submission/facets/submission').json()['mitigation_sector']


def test_case_variants_are_one_option_matching_both(client):
    for title, sector in [('a', 'Energy'), ('b', 'Energy'), ('c', 'ENERGY')]:
        s = SubmissionFactory(title=title, intervention_measurement='Mitigation')
        MitigationFactory(submission_id=s.id, sector=sector)

    sectors = client.get('/submission/facets/submission').json()['mitigation_sector']
    assert sectors == ['Energy']                      # most common spelling wins
    assert _titles(client, mitigation_sector='Energy') == {'a', 'b', 'c'}

    by_sector = client.get('/report/summary').json()['mitigation_sectors']
    assert by_sector == [{'label': 'Energy', 'count': 3}]


def _user_id(client):
    import jwt
    return int(jwt.decode(client.headers['Authorization'].split()[1], options={'verify_signature': False})['sub'])


def test_mine_shows_only_the_callers_submissions_everywhere(client, api):
    other = api(email='other@example.org')
    SubmissionFactory(title='mine', createdby=_user_id(client))
    SubmissionFactory(title='theirs', createdby=_user_id(other))
    SubmissionFactory(title='legacy import', createdby=None)

    assert _titles(client, mine='true') == {'mine'}
    assert _titles(other, mine='true') == {'theirs'}
    assert _titles(client) == {'mine', 'theirs', 'legacy import'}
    assert client.get('/report/summary', params={'mine': 'true'}).json()['total'] == 1
    export = client.get('/report/export', params={'mine': 'true', 'format': 'csv'})
    rows = list(csv.reader(io.StringIO(export.content.decode('utf-8-sig'))))
    assert export.status_code == 200 and [r[1] for r in rows[1:]] == ['mine']


def test_mine_requires_login(client):
    anonymous = client.get('/submission/list_submission', params={'mine': 'true'}, headers={'Authorization': ''})
    assert anonymous.status_code == 401


def test_budget_range_and_regional_policy_filters(client):
    a = SubmissionFactory(title='a', estimated_budget_cost='R1m - R5m', intervention_measurement='Mitigation')
    MitigationFactory(submission_id=a.id, provincial_municipal=' City of Joburg ')
    b = SubmissionFactory(title='b', estimated_budget_cost='> R100m', intervention_measurement='Adaptation')
    AdaptationFactory(submission_id=b.id, provincial_municipal="[{'term': 'Biodiversity Sector & Management Plan'}]")

    facets = client.get('/submission/facets/submission').json()
    assert facets['estimated_budget_cost'] == ['> R100m', 'R1m - R5m']
    assert facets['mitigation_regional_policy'] == ['City of Joburg']
    assert facets['adaptation_regional_policy'] == ['Biodiversity Sector & Management Plan']

    assert _titles(client, estimated_budget_cost='R1m - R5m') == {'a'}
    assert _titles(client, mitigation_regional_policy='City of Joburg') == {'a'}
    assert _titles(client, adaptation_regional_policy='Biodiversity Sector & Management Plan') == {'b'}


def test_province_filter_ignores_case(client):
    SubmissionFactory(title='form', geo_location={'province': 'Kwazulu-Natal'})          # region-table spelling
    SubmissionFactory(title='legacy', geo_location={'province': [{'term': 'KwaZulu-Natal'}]})
    SubmissionFactory(title='other', geo_location={'province': 'Gauteng'})

    assert _titles(client, province='KwaZulu-Natal') == {'form', 'legacy'}
    # One option for both spellings (which spelling labels it is a tie here).
    assert [p.casefold() for p in client.get('/submission/facets/submission').json()['province']] == ['gauteng', 'kwazulu-natal']
