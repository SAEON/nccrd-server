from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException
from fastapi.openapi.models import OAuth2, OAuthFlowClientCredentials, OAuthFlows
from fastapi.security.base import SecurityBase
from fastapi.security.utils import get_authorization_scheme_param
from starlette.requests import Request
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN

from nccrd.const import NCCRDScope
from odp.config import config
from odp.lib.hydra import HydraAdminAPI, OAuth2TokenIntrospection

hydra_admin_api = HydraAdminAPI(config.HYDRA.ADMIN.URL)
hydra_public_url = config.HYDRA.PUBLIC.URL


@dataclass
class Authorized:
    """An Authorized object represents a statement that permission is
    granted for usage of the requested scope by the specified client
    and (if a user-initiated API call) the specified user. If such
    permission is denied, an HTTP 403 error is raised instead.
    """
    client_id: str
    user_id: Optional[str]


def _authorize_request(request: Request, required_scope: NCCRDScope):
    auth_header = request.headers.get('Authorization')
    scheme, access_token = get_authorization_scheme_param(auth_header)
    if not auth_header or scheme.lower() != 'bearer':
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            headers={'WWW-Authenticate': 'Bearer'},
        )

    token: OAuth2TokenIntrospection = hydra_admin_api.introspect_token(
        access_token, [required_scope.value],
    )

    if not token.active:
        raise HTTPException(HTTP_403_FORBIDDEN)

    return Authorized(
        client_id=token.client_id,
        user_id=None if token.sub == token.client_id else token.sub
    )


class BaseAuthorize(SecurityBase):

    def __init__(self):
        # OpenAPI docs / Swagger auth
        self.scheme_name = 'ODP API Authorization'
        self.model = OAuth2(flows=OAuthFlows(clientCredentials=OAuthFlowClientCredentials(
            tokenUrl=f'{hydra_public_url}/oauth2/token',
            scopes={s.value: s.value for s in NCCRDScope},
        )))

    def __repr__(self):
        return f'{self.__class__.__name__}()'


class Authorize(BaseAuthorize):
    def __init__(self, scope: NCCRDScope):
        super().__init__()
        self.scope = scope

    def __repr__(self):
        return f'{self.__class__.__name__}(scope={self.scope.value!r})'

    async def __call__(self, request: Request) -> Authorized:
        return _authorize_request(request, self.scope)

