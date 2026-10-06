"""
Only reviewed (Accepted) projects are public. Submitters see their own
projects in every state, reviewers see and decide the queue, and an owner's
edit sends a published project back for review.
"""
import jwt
import pytest

from nccrd.db.models import Submission
from nccrd.db.models.rbac import Tenant
from test import TestSession
from test.factories import FactorySession, MitigationFactory, SubmissionFactory


def _uid(client):
    return int(jwt.decode(client.headers['Authorization'].split()[1], options={'verify_signature': False})['sub'])


@pytest.fixture
def tenant():
    t = Tenant(hostname='test.nccrd.localhost', title='Test', is_default=True, include_unbounded_submissions=True)
    FactorySession.add(t)
    FactorySession.commit()
    return t


@pytest.fixture
def owner(api, tenant):
    return api(email='owner@example.org', permissions=['create-submission'])


@pytest.fixture
def reviewer(api, tenant):
    return api(email='reviewer@example.org', permissions=['validate-submission', 'update-submission'])


@pytest.fixture
def projects(owner):
    uid = _uid(owner)
    return {
        'published': SubmissionFactory(title='published', createdby=uid),
        'pending': SubmissionFactory(title='pending', createdby=uid, submission_status='Pending'),
        'rejected': SubmissionFactory(title='rejected', createdby=uid, submission_status='Not Accepted'),
        'draft': SubmissionFactory(title='draft', createdby=uid, issubmitted=False, submission_status=None),
    }


def _titles(client, **params):
    r = client.get('/submission/list_submission', params=params)
    assert r.status_code == 200, r.text
    return {s['title'] for s in r.json()}


def test_public_sees_only_published(api, tenant, projects):
    assert _titles(api(email='visitor@example.org')) == {'published'}
    assert api().get('/report/summary').json()['total'] == 1


def test_owner_sees_all_their_own(owner, projects):
    assert _titles(owner, mine='true') == {'published', 'pending', 'rejected', 'draft'}
    assert _titles(owner, mine='true', review_status='not_accepted') == {'rejected'}


def test_queue_tabs_are_reviewer_only(owner, reviewer, projects):
    assert owner.get('/submission/list_submission', params={'review_status': 'awaiting_review'}).status_code == 403
    assert _titles(reviewer, review_status='awaiting_review') == {'pending'}
    assert _titles(reviewer, review_status='draft') == {'draft'}
    counts = reviewer.get('/submission/review/counts').json()
    assert counts == {'published': 1, 'awaiting_review': 1, 'not_accepted': 1, 'draft': 1, 'all': 4}
    assert owner.get('/submission/review/counts').status_code == 403


def test_unpublished_detail_hidden_from_others(api, owner, reviewer, projects):
    pending = projects['pending'].id
    assert api(email='visitor@example.org').get(f'/submission/read_submission/{pending}').status_code == 404
    assert owner.get(f'/submission/read_submission/{pending}').status_code == 200
    assert reviewer.get(f'/submission/read_submission/{pending}').status_code == 200


def test_reviewer_accepts_and_not_accepts_with_reason(api, reviewer, projects):
    pending, draft = projects['pending'].id, projects['draft'].id

    assert reviewer.post(f'/submission/{pending}/review', json={'decision': 'Not accepted'}).status_code == 422
    r = reviewer.post(f'/submission/{pending}/review', json={'decision': 'Not accepted', 'comments': ' Add a budget '})
    assert r.status_code == 200 and r.json()['submission_comments'] == 'Add a budget'

    assert reviewer.post(f'/submission/{draft}/review', json={'decision': 'Accepted'}).json()['published'] is True
    assert _titles(api(email='visitor@example.org')) == {'published', 'draft'}

    detail = reviewer.get(f'/submission/read_submission/{pending}').json()
    assert detail['reviewed_by'] == 'Test User' and detail['submission_status'] == 'Not accepted'


def test_only_reviewers_can_decide(owner, projects):
    r = owner.post(f"/submission/{projects['pending'].id}/review", json={'decision': 'Accepted'})
    assert r.status_code == 403


def _edit(client, submission, **body):
    MitigationFactory(submission_id=submission.id)
    return client.patch(f'/submission/update_new_submission/{submission.id}', json={'title': 'Edited', **body})


def test_owner_edit_goes_back_to_review_and_cannot_self_publish(owner, projects):
    r = _edit(owner, projects['published'], submission_status='Accepted', createdby=999)
    assert r.status_code == 200, r.text
    saved = TestSession.get(Submission, projects['published']._id)
    assert (saved.title, saved.submission_status, saved.createdby) == ('Edited', 'Pending', _uid(owner))


def test_curator_edit_keeps_published(reviewer, projects):
    assert _edit(reviewer, projects['published']).status_code == 200
    assert TestSession.get(Submission, projects['published']._id).submission_status == 'Accepted'


def test_cannot_edit_someone_elses_project(api, tenant, projects):
    stranger = api(email='stranger@example.org', permissions=['create-submission'])
    assert _edit(stranger, projects['published']).status_code == 403
