"""
A site's admin edits its names, contact address, colour, About texts and
images in the app (permission edit-site), on their own site only.
"""
import pytest

import nccrd.api.routers.site as site_router
from test.api.test_user_management import client, person
from test.factories import FactorySession
from nccrd.db.models.rbac import Permission, PermissionXrefRole, Role, Tenant

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64


@pytest.fixture
def sites():
    national = Tenant(hostname='test.nccrd.localhost', title='National', short_title='NCCRD', is_default=True)
    mccrd = Tenant(hostname='mccrd.example.org', title='Mpumalanga Climate Change Response Database', short_title='MCCRD',
                   slug='mccrd', province='Mpumalanga', theme={'accent-primary': '#622700', 'chart-series': '#0a51a5'},
                   front_matter={'about': {'title': 'Welcome', 'content': 'Old text'},
                                 'context': {'title': 'Climate change in Mpumalanga', 'content': 'Coal.'}},
                   hero_image={'url': '/sites/mccrd/hero.jpg', 'credit': 'Someone'})
    gccrd = Tenant(hostname='gccrd.example.org', title='Gauteng', short_title='GCCRD', slug='gccrd', province='Gauteng')
    FactorySession.add_all([national, mccrd, gccrd])
    FactorySession.commit()
    return {'national': national, 'mccrd': mccrd, 'gccrd': gccrd}


@pytest.fixture
def editor_role():
    role = Role(name='site-admin')
    permission = Permission(name='edit-site')
    FactorySession.add_all([role, permission])
    FactorySession.flush()
    FactorySession.add(PermissionXrefRole(permission_id=permission.id, role_id=role.id))
    FactorySession.commit()
    return role


@pytest.fixture
def mp_admin(sites, editor_role):
    return client(person('mp.admin@example.org', (editor_role, sites['mccrd'])), sites['mccrd'])


@pytest.fixture(autouse=True)
def upload_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(site_router, 'SITE_UPLOAD_DIR', tmp_path)
    return tmp_path


def test_admin_edits_texts_names_contact_and_colour(mp_admin):
    r = mp_admin.put('/site', json={
        'title': ' Mpumalanga Climate Change Response Database (MCCRD) ',
        'contact_email': 'mccrd@mpg.gov.za',
        'colour': '#1A5C2E',
        'sections': {'about': {'title': 'Welcome to the MCCRD', 'content': 'First paragraph.\n\nSecond paragraph.'}},
        'hero_credit': {'credit': 'Provincial photographer', 'license': 'Used with permission'},
    })
    assert r.status_code == 200, r.text
    site = mp_admin.get('/site').json()
    assert site['title'] == 'Mpumalanga Climate Change Response Database (MCCRD)'
    assert site['contact_email'] == 'mccrd@mpg.gov.za'
    assert site['theme']['accent-primary'] == '#1a5c2e'
    assert site['theme']['accent-secondary'] == '#357047'  # 12% lighter
    assert site['theme']['chart-series'] == '#0a51a5'  # kept
    assert site['front_matter']['about'] == {'title': 'Welcome to the MCCRD', 'content': 'First paragraph.\n\nSecond paragraph.'}
    assert site['front_matter']['context']['content'] == 'Coal.'  # untouched sections stay
    assert site['hero_image'] == {'url': '/sites/mccrd/hero.jpg', 'credit': 'Provincial photographer',
                                  'license': 'Used with permission', 'source_url': None, 'license_url': None}


@pytest.mark.parametrize('body', [
    {'colour': 'red'},
    {'contact_email': 'not an email'},
    {'sections': {'sidebar': {'title': 'Nope', 'content': ''}}},
    {'hero_credit': {'source_url': 'javascript:alert(1)'}},
    {'short_title': 'X' * 21},
])
def test_bad_values_are_refused(mp_admin, body):
    assert mp_admin.put('/site', json=body).status_code == 422


def test_only_the_sites_own_admins_edit_it(sites, editor_role, api):
    mp_admin = person('mp.admin@example.org', (editor_role, sites['mccrd']))
    assert client(mp_admin, sites['gccrd']).put('/site', json={'title': 'Hijacked'}).status_code == 403
    assert client(mp_admin).put('/site', json={'title': 'Hijacked'}).status_code == 403
    nobody = person('nobody@example.org')
    assert client(nobody, sites['mccrd']).put('/site', json={'title': 'Hijacked'}).status_code == 403

    # A national site-admin edits any site.
    national_admin = person('admin@example.org', (editor_role, sites['national']))
    assert client(national_admin, sites['gccrd']).put('/site', json={'title': 'Gauteng CCRD'}).status_code == 200


def test_images_upload_and_are_served(mp_admin, upload_dir):
    r = mp_admin.post('/site/images/logo', files={'file': ('arms.png', PNG, 'image/png')})
    assert r.status_code == 200, r.text
    logo = r.json()['logo_url']
    assert logo.startswith('/uploads/sites/') and logo.endswith('.png')
    assert (upload_dir / logo.split('/uploads/sites/')[1]).read_bytes() == PNG

    hero = mp_admin.post('/site/images/hero', files={'file': ('view.jpg', JPEG, 'image/jpeg')}).json()['hero_image']
    assert hero['url'].endswith('.jpg') and hero['credit'] == 'Someone'

    assert mp_admin.delete('/site/images/flag').json()['flag_url'] is None
    assert mp_admin.delete('/site/images/hero').json()['hero_image'] is None


@pytest.mark.parametrize('name, data', [
    ('evil.svg', b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'),
    ('fake.png', b'GIF89a not really a png'),
    ('page.html', b'<html><script>alert(1)</script></html>'),
])
def test_only_raster_images_are_accepted(mp_admin, name, data):
    r = mp_admin.post('/site/images/logo', files={'file': (name, data, 'image/png')})
    assert r.status_code == 422


def test_large_images_are_refused(mp_admin, monkeypatch):
    monkeypatch.setattr(site_router, 'MAX_SITE_IMAGE_BYTES', 32)
    assert mp_admin.post('/site/images/logo', files={'file': ('arms.png', PNG, 'image/png')}).status_code == 413
