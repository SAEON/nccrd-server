"""
Two people capturing at once must neither be logged out mid-session nor
silently overwrite each other's edits.
"""
from datetime import datetime, timedelta, timezone

import jwt

from nccrd.config import nccrd_config
from nccrd.db.models import Submission
from test import TestSession
from test.factories import SubmissionFactory

LOADED_AT = datetime(2026, 9, 30, 8, 0, 0, 123456)


def _expired_token(user_id: int) -> str:
    return jwt.encode(
        {"sub": str(user_id), "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        nccrd_config.NCCRD.JWT_SECRET,
        algorithm=nccrd_config.NCCRD.JWT_ALGORITHM,
    )


def test_refresh_issues_a_new_working_token(api):
    client = api()
    r = client.post('/auth/refresh')
    assert r.status_code == 200, r.text
    token = r.json()['access_token']

    me = client.get('/rbac/me', headers={'Authorization': f'Bearer {token}'})
    assert me.status_code != 401


def test_refresh_rejects_an_expired_token(api):
    client = api()
    user_id = jwt.decode(client.headers['Authorization'].split()[1], options={'verify_signature': False})['sub']
    r = client.post('/auth/refresh', headers={'Authorization': f'Bearer {_expired_token(int(user_id))}'})
    assert r.status_code == 401


def _patch(client, submission, **body):
    return client.patch(f'/submission/update_new_submission/{submission.id}', json={'title': 'Edited', **body})


def test_update_with_current_updatedate_succeeds(api):
    client = api(permissions=['update-submission'])
    s = SubmissionFactory(intervention_measurement='Mitigation', updatedate=LOADED_AT)

    r = _patch(client, s, expected_updatedate=LOADED_AT.isoformat())
    assert r.status_code == 200, r.text
    assert TestSession.get(Submission, s._id).title == 'Edited'


def test_update_after_someone_else_saved_is_rejected(api):
    client = api(permissions=['update-submission'])
    s = SubmissionFactory(intervention_measurement='Mitigation', title='Theirs', updatedate=LOADED_AT + timedelta(minutes=5))

    r = _patch(client, s, expected_updatedate=LOADED_AT.isoformat())
    assert r.status_code == 409
    assert r.json()['detail']['updatedate'].startswith('2026-09-30T08:05:00')
    assert TestSession.get(Submission, s._id).title == 'Theirs'


def test_never_saved_submission_matches_null_expected(api):
    client = api(permissions=['update-submission'])
    s = SubmissionFactory(intervention_measurement='Mitigation', updatedate=None)

    assert _patch(client, s, expected_updatedate=None).status_code == 200


def test_update_without_expected_updatedate_skips_the_check(api):
    client = api(permissions=['update-submission'])
    s = SubmissionFactory(intervention_measurement='Mitigation', updatedate=LOADED_AT)

    assert _patch(client, s).status_code == 200
