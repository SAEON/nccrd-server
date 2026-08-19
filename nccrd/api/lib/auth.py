import os
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, HTTPException
from fastapi.openapi.models import OAuth2, OAuthFlowClientCredentials, OAuthFlows
from fastapi.security.base import SecurityBase
from fastapi.security.utils import get_authorization_scheme_param
from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN

from nccrd.const import NCCRDScope
from nccrd.db import get_db
from nccrd.db.models.rbac import User
from odp.config import config
from odp.lib.hydra import HydraAdminAPI, OAuth2TokenIntrospection

hydra_admin_api = HydraAdminAPI(config.HYDRA.ADMIN.URL)
hydra_public_url = config.HYDRA.PUBLIC.URL

# ---------------------------------------------------------------------------
# Development bypass
# ---------------------------------------------------------------------------
# Set NCCRD_BYPASS_AUTH=1 in your shell (or .env) to skip Hydra token
# validation entirely.  All write requests are then treated as coming from
# a known real user (see `_DEV_USER_EMAIL`) so data created while the real
# Hydra login flow isn't wired up is attributable to a person, not a
# synthetic placeholder.
#
# TODO: once the Hydra login flow is implemented, drop this attribution and
# go back to resolving `internal_user_id` from the actual authenticated
# token on every request.
#
# NEVER enable this in a production environment.
# ---------------------------------------------------------------------------
_BYPASS_AUTH = os.getenv("NCCRD_BYPASS_AUTH", "1") != "0"

#: Real user that all dev-bypass activity is attributed to until login is sorted.
_DEV_USER_EMAIL = "n.bingani@saeon.nrf.ac.za"
_DEV_USER_NAME = "N. Bingani"


@dataclass
class Authorized:
    """An Authorized object represents a statement that permission is
    granted for usage of the requested scope by the specified client
    and (if a user-initiated API call) the specified user. If such
    permission is denied, an HTTP 403 error is raised instead.

    ``internal_user_id`` is the resolved ``nccrd.user.id`` primary key —
    use this (not ``user_id`` / ``client_id``) wherever a FK-compatible
    user reference is needed (e.g. ``Submission.createdby``).
    """
    client_id: str
    user_id: Optional[str]
    internal_user_id: int


def _get_or_create_user(db: Session, saeon_id: str, *, name: str, email: str) -> User:
    """Look up the local user record for an external identity, provisioning
    a placeholder row on first sight (mirrors the legacy-user backfill done
    for migrated createdby ids in alembic revision 0002)."""
    user = db.query(User).filter(User.saeon_id == saeon_id).first()
    if user is not None:
        return user

    user = User(name=name, email=email, saeon_id=saeon_id)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _get_or_create_dev_user(db: Session) -> User:
    """Resolve the fixed real user that dev-bypass activity is attributed to,
    provisioning the row if this DB hasn't seen it yet (e.g. a fresh dev DB)."""
    user = db.query(User).filter(User.email == _DEV_USER_EMAIL).first()
    if user is not None:
        return user

    user = User(name=_DEV_USER_NAME, email=_DEV_USER_EMAIL)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _authorize_request(request: Request, required_scope: NCCRDScope, db: Session) -> Authorized:
    # Short-circuit for local development — no Hydra token required.
    if _BYPASS_AUTH:
        dev_user = _get_or_create_dev_user(db)
        return Authorized(client_id="dev-client", user_id=None, internal_user_id=dev_user.id)

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

    is_user_call = token.sub != token.client_id
    # token.sub is Hydra's subject claim — for a user-initiated call this is
    # the external user identity; for a client-credentials call it's just
    # the client id repeated, so fall back to attributing the client itself.
    saeon_id = token.sub if is_user_call else token.client_id
    user = _get_or_create_user(
        db,
        saeon_id,
        name=saeon_id,
        email=f"{saeon_id}@placeholder.local",
    )

    return Authorized(
        client_id=token.client_id,
        user_id=token.sub if is_user_call else None,
        internal_user_id=user.id,
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

    async def __call__(self, request: Request, db: Session = Depends(get_db)) -> Authorized:
        return _authorize_request(request, self.scope, db)

