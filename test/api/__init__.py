def assert_forbidden(response):
    assert response.status_code == 403
