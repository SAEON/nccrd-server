"""
Email: a forgotten password is reset through an emailed link, and people hear
when their account request or project is decided.
"""
import re
from email.message import EmailMessage

import jwt
import pytest

import nccrd.api.lib.auth
import nccrd.api.lib.mail
import nccrd.api.routers.auth
from nccrd.api.lib.auth import create_access_token, hash_password
from nccrd.config import nccrd_config
from nccrd.db.models.rbac import Role, Tenant, User
from test import TestSession
from test.factories import FactorySession, SubmissionFactory

SITE = 'https://nccrd.example.org'
PASSWORD = 'the-old-password'


@pytest.fixture
def outbox(monkeypatch):
    """Mail set up, with every message caught here instead of sent."""
    sent = []
    mail = nccrd_config.NCCRD.MAIL
    monkeypatch.setattr(mail, 'HOST', 'smtp.example.org')
    monkeypatch.setattr(mail, 'USERNAME', 'ict@example.org')
    monkeypatch.setattr(nccrd_config.NCCRD, 'UI_URL', SITE)
    monkeypatch.setattr(nccrd.api.lib.mail, '_deliver', sent.append)
    monkeypatch.setattr(nccrd.api.routers.auth, '_last_reset_mail', {})
    return sent


@pytest.fixture
def tenant():
    t = Tenant(hostname='test.nccrd.localhost', title='National Climate Change Response Database',
               short_title='NCCRD', is_default=True, include_unbounded_submissions=True,
               contact_email='nccrd@example.org')
    FactorySession.add(t)
    FactorySession.commit()
    return t


@pytest.fixture
def member(tenant):
    user = User(name='Thandi M', email='thandi@example.org', password_hash=hash_password(PASSWORD))
    FactorySession.add(user)
    FactorySession.commit()
    return user


def _anonymous(api):
    return api(email='visitor@example.org')


def _post(client, path, headers=None, **kwargs):
    return client.post(path, headers={'Authorization': '', **(headers or {})}, **kwargs)


def _login(client, password, email='thandi@example.org'):
    return _post(client, '/auth/login', json={'email': email, 'password': password})


def _token(message: EmailMessage) -> str:
    return re.search(r'/reset-password#token=(\S+)', message.get_content()).group(1)


def test_forgotten_password_is_reset_from_the_emailed_link(api, member, outbox):
    client = _anonymous(api)
    r = _post(client, '/auth/forgot-password', json={'email': ' Thandi@Example.org '})
    assert r.status_code == 202

    [message] = outbox
    assert message['To'] == 'thandi@example.org'
    assert message['From'] == 'NCCRD <ict@example.org>'
    assert f'{SITE}/reset-password#token=' in message.get_content()

    token = _token(message)
    r = _post(client, '/auth/reset-password', json={'token': token, 'new_password': 'a-new-password'})
    assert r.status_code == 200, r.text
    assert _login(client, 'a-new-password').status_code == 200
    assert _login(client, PASSWORD).status_code == 401

    # A link works once.
    r = _post(client, '/auth/reset-password', json={'token': token, 'new_password': 'another-password'})
    assert r.status_code == 400
    assert 'expired or has already been used' in r.json()['detail']


def test_reply_is_the_same_and_nothing_is_sent_for_an_unknown_or_unapproved_email(api, member, outbox):
    FactorySession.add(User(name='Pending', email='pending@example.org', registration_status='pending',
                            password_hash=hash_password(PASSWORD)))
    FactorySession.commit()
    client = _anonymous(api)
    known = _post(client, '/auth/forgot-password', json={'email': 'thandi@example.org'})
    unknown = _post(client, '/auth/forgot-password', json={'email': 'nobody@example.org'})
    pending = _post(client, '/auth/forgot-password', json={'email': 'pending@example.org'})
    assert known.status_code == unknown.status_code == pending.status_code == 202
    assert known.json() == unknown.json() == pending.json()
    assert [m['To'] for m in outbox] == ['thandi@example.org']


def test_one_reset_email_a_minute(api, member, outbox):
    client = _anonymous(api)
    for _ in range(3):
        assert _post(client, '/auth/forgot-password', json={'email': 'thandi@example.org'}).status_code == 202
    assert len(outbox) == 1


def test_link_goes_to_the_province_site_it_was_asked_from(api, member, outbox):
    FactorySession.add(Tenant(hostname='mccrd.example.org', title='Mpumalanga Climate Change Response Database',
                              short_title='MCCRD', slug='mccrd', province='Mpumalanga'))
    FactorySession.commit()
    _post(_anonymous(api), '/auth/forgot-password', json={'email': 'thandi@example.org'},
          headers={'X-NCCRD-Site-Province': 'mpumalanga'})
    [message] = outbox
    assert message['Subject'] == 'Set a new password for MCCRD'
    assert message['From'] == 'MCCRD <ict@example.org>'
    assert f'{SITE}/mpumalanga/reset-password#token=' in message.get_content()


def test_without_a_site_address_the_link_uses_a_trusted_browser_origin_only(api, member, outbox, monkeypatch):
    monkeypatch.setattr(nccrd_config.NCCRD, 'UI_URL', None)
    client = _anonymous(api)
    _post(client, '/auth/forgot-password', json={'email': 'thandi@example.org'},
          headers={'Origin': 'https://evil.example.com'})
    assert outbox == []

    monkeypatch.setattr(nccrd.api.routers.auth, '_last_reset_mail', {})
    _post(client, '/auth/forgot-password', json={'email': 'thandi@example.org'},
          headers={'Origin': 'http://localhost:5174'})
    [message] = outbox
    assert 'http://localhost:5174/reset-password#token=' in message.get_content()


def test_reset_link_and_access_token_cannot_stand_in_for_each_other(api, member, outbox):
    client = _anonymous(api)
    _post(client, '/auth/forgot-password', json={'email': 'thandi@example.org'})
    reset_token = _token(outbox[0])

    r = client.get('/rbac/me', headers={'Authorization': f'Bearer {reset_token}'})
    assert r.status_code == 401

    r = _post(client, '/auth/reset-password', json={'token': create_access_token(member), 'new_password': 'a-new-password'})
    assert r.status_code == 400
    r = _post(client, '/auth/reset-password', json={'token': 'not-a-token', 'new_password': 'a-new-password'})
    assert r.status_code == 400


def test_expired_link_is_refused(api, member, outbox, monkeypatch):
    monkeypatch.setattr(nccrd.api.lib.auth, 'PASSWORD_RESET_MINUTES', -1)
    client = _anonymous(api)
    _post(client, '/auth/forgot-password', json={'email': 'thandi@example.org'})
    r = _post(client, '/auth/reset-password', json={'token': _token(outbox[0]), 'new_password': 'a-new-password'})
    assert r.status_code == 400
    assert _login(client, PASSWORD).status_code == 200


def test_short_new_password_is_refused(api, member, outbox):
    client = _anonymous(api)
    _post(client, '/auth/forgot-password', json={'email': 'thandi@example.org'})
    r = _post(client, '/auth/reset-password', json={'token': _token(outbox[0]), 'new_password': 'short'})
    assert r.status_code == 422


def test_without_mail_set_up_nothing_is_sent_and_the_reply_is_the_same(api, member, outbox, monkeypatch, caplog):
    monkeypatch.setattr(nccrd_config.NCCRD.MAIL, 'HOST', None)
    r = _post(_anonymous(api), '/auth/forgot-password', json={'email': 'thandi@example.org'})
    assert r.status_code == 202
    assert outbox == []
    assert 'Mail is not set up' in caplog.text


def test_nothing_is_sent_without_a_sender_address(monkeypatch, caplog):
    mail = nccrd_config.NCCRD.MAIL
    for key, value in dict(HOST='smtp.example.org', USERNAME=None, FROM=None).items():
        monkeypatch.setattr(mail, key, value)
    monkeypatch.setattr(nccrd.api.lib.mail, '_deliver', lambda message: pytest.fail('sent'))
    assert nccrd.api.lib.mail.send_mail('a@example.org', 'Hello', 'Body') is False
    assert 'no sender address' in caplog.text


def test_mail_server_failure_is_logged_not_raised(monkeypatch, caplog):
    monkeypatch.setattr(nccrd_config.NCCRD.MAIL, 'HOST', 'smtp.example.org')
    monkeypatch.setattr(nccrd_config.NCCRD.MAIL, 'FROM', 'ict@example.org')

    def refuse(message):
        raise ConnectionRefusedError('no route')

    monkeypatch.setattr(nccrd.api.lib.mail, '_deliver', refuse)
    assert nccrd.api.lib.mail.send_mail('a@example.org', 'Hello', 'Body') is False
    assert 'Could not send the email' in caplog.text


def test_delivery_uses_starttls_and_logs_in(monkeypatch):
    mail = nccrd_config.NCCRD.MAIL
    for key, value in dict(HOST='smtp.example.org', PORT=587, TLS=True, SSL=False,
                           USERNAME='ict@example.org', PASSWORD='secret', FROM=None).items():
        monkeypatch.setattr(mail, key, value)
    calls = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            calls.append(('connect', host, port))

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            calls.append(('quit',))

        def starttls(self, context):
            calls.append(('starttls',))

        def login(self, user, password):
            calls.append(('login', user, password))

        def send_message(self, message):
            calls.append(('send', message['To'], message['From']))

    monkeypatch.setattr(nccrd.api.lib.mail.smtplib, 'SMTP', FakeSMTP)
    assert nccrd.api.lib.mail.send_mail('a@example.org', 'Hello', 'Body') is True
    assert calls == [
        ('connect', 'smtp.example.org', 587),
        ('starttls',),
        ('login', 'ict@example.org', 'secret'),
        ('send', 'a@example.org', 'NCCRD <ict@example.org>'),
        ('quit',),
    ]


# ── Account requests ──────────────────────────────────────────────────────────


@pytest.fixture
def admin(api, tenant):
    FactorySession.add(Role(name='user'))
    FactorySession.commit()
    return api(email='admin@example.org', permissions=['assign-role'])


def _request_account(admin, email):
    _post(admin, '/auth/register', json={
        'name': 'Sipho K', 'email': email, 'organisation': 'City', 'password': 'a-long-password',
        'accept_privacy_notice': True,
    })
    return TestSession.query(User).filter(User.email == email).one().id


def test_approved_and_rejected_requests_are_told(admin, outbox):
    role_id = TestSession.query(Role).filter(Role.name == 'user').one().id
    approved = _request_account(admin, 'sipho@example.org')
    rejected = _request_account(admin, 'lerato@example.org')
    # Asking tells the site's admins.
    assert [(m['To'], m['Subject']) for m in outbox] == [('admin@example.org', 'New account request on NCCRD')] * 2
    assert f'Review it at {SITE}/admin/registrations' in outbox[0].get_content()
    outbox.clear()

    assert admin.post(f'/rbac/registrations/{approved}/approve', json={'role_id': role_id}).status_code == 200
    assert admin.post(f'/rbac/registrations/{rejected}/reject').status_code == 200

    yes, no = outbox
    assert (yes['To'], yes['Subject']) == ('sipho@example.org', 'Your NCCRD account is ready')
    assert f'Log in at {SITE}/login' in yes.get_content()
    assert (no['To'], no['Subject']) == ('lerato@example.org', 'Your NCCRD account request')
    assert 'contact the NCCRD team at nccrd@example.org' in no.get_content()


# ── Project reviews ───────────────────────────────────────────────────────────


@pytest.fixture
def reviewer(api, tenant):
    return api(email='reviewer@example.org', permissions=['validate-submission'])


def test_submitter_is_told_the_review_outcome_once(reviewer, member, outbox):
    project = SubmissionFactory(title='Solar pumps', createdby=member.id, submission_status='Pending',
                                data_source='react_app')

    r = reviewer.post(f'/submission/{project.id}/review', json={'decision': 'Not accepted', 'comments': 'Add a budget'})
    assert r.status_code == 200, r.text
    r = reviewer.post(f'/submission/{project.id}/review', json={'decision': 'Not accepted', 'comments': 'Add a budget'})
    assert r.status_code == 200
    r = reviewer.post(f'/submission/{project.id}/review', json={'decision': 'Accepted'})
    assert r.status_code == 200

    changes, published = outbox
    assert changes['To'] == 'thandi@example.org'
    assert changes['Subject'] == 'Your project on NCCRD needs changes'
    assert 'Add a budget' in changes.get_content()
    assert published['Subject'] == 'Your project is published on NCCRD'
    assert f'{SITE}/submission/{project.id}' in published.get_content()


def test_imported_projects_send_nothing(reviewer, member, outbox):
    project = SubmissionFactory(createdby=member.id, submission_status='Pending', data_source='sqlserver_legacy')
    assert reviewer.post(f'/submission/{project.id}/review', json={'decision': 'Accepted'}).status_code == 200
    assert outbox == []


def test_reset_link_is_signed_for_its_purpose(member):
    """Signed with more than the secret alone, so the JWT secret can't verify it."""
    token = nccrd.api.lib.auth.create_password_reset_token(member)
    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(token, nccrd_config.NCCRD.JWT_SECRET, algorithms=['HS256'])


@pytest.mark.parametrize('source, made_here', [
    (None, True), ('react_app', True), ('bulk_upload: projects.xlsx', True),
    ('sqlserver_legacy', False), ('gauteng_register_2024', False),
])
def test_projects_made_in_the_app_are_told_apart_from_imported_ones(source, made_here):
    from nccrd.api.routers.submission import made_in_app
    from nccrd.db.models import Submission
    assert made_in_app(Submission(data_source=source)) is made_here
