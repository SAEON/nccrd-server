import nccrd.api
from random import randint, choice
from collections import namedtuple

from odp.lib.hydra import HydraAdminAPI
from test.api import all_scopes_excluding

from nccrd.const import NCCRDScope

from starlette.testclient import TestClient
import pytest

MockToken = namedtuple('MockToken', ('active', 'client_id', 'sub'))


@pytest.fixture(params=['client_credentials', 'authorization_code'])
def api(request, monkeypatch):
    """Fixture returning an API test client constructor. Example usages::

        r = api(scopes).get('/catalog/')

        r = api(scopes, user_collections=authorized_collections).post('/record/', json=dict(
            doi=record.doi,
            metadata=record.metadata_,
            ...,
        ))

    Each parameterization of the calling test is invoked twice: first
    to simulate a machine client with a client_credentials grant; second
    to simulate a UI client with an authorization_code grant.

    :param scopes: iterable of ODPScope granted to the test client/user
    """

    def api_test_client(
            scopes: list[NCCRDScope],
            *,
            client_id: str = 'nccrd.test.client',
            role_id: str = 'nccrd.test.role',
            user_id: str = 'nccrd.test.user'
    ):
        monkeypatch.setattr(HydraAdminAPI, 'introspect_token', lambda _, access_token, required_scopes: MockToken(
            active=required_scopes[0] in scopes,
            client_id=client_id,
            sub=user_id if request.param == 'authorization_code' else client_id,
        ))

        return TestClient(
            app=nccrd.api.app,
            headers={
                'Accept': 'application/json',
                'Authorization': 'Bearer t0k3n',
            }
        )

    api_test_client.grant_type = request.param
    return api_test_client


@pytest.fixture(params=['scope_match', 'scope_mismatch'])
def scopes(request):
    """Fixture for parameterizing the set of auth scopes
    to be associated with the API test client.

    The test function must be decorated to indicate the scope
    required by the API route::

        @pytest.mark.require_scope(ODPScope.CATALOG_READ)

    This has the same effect as parameterizing the test function
    as follows::

        @pytest.mark.parametrize('scopes', [
            [ODPScope.CATALOG_READ],
            all_scopes_excluding(ODPScope.CATALOG_READ),
        ])

    """
    scope = request.node.get_closest_marker('require_scope').args[0]

    if request.param == 'scope_match':
        return [scope]
    elif request.param == 'scope_mismatch':
        return all_scopes_excluding(scope)
