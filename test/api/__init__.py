from nccrd.const import NCCRDScope


def all_scopes_excluding(scope):
    return [s for s in NCCRDScope if s != scope]


def assert_forbidden(response):
    assert response.status_code == 403
    assert response.json() == {'detail': 'Forbidden'}

