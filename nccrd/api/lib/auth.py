import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer
from fastapi.security.utils import get_authorization_scheme_param
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.status import HTTP_401_UNAUTHORIZED

from nccrd.config import nccrd_config
from nccrd.db import get_db
from nccrd.db.models.rbac import User

# ---------------------------------------------------------------------------
# Development bypass
# ---------------------------------------------------------------------------
# Set NCCRD_BYPASS_AUTH=1 in your shell (or .env) to skip JWT validation
# entirely. All requests are then treated as coming from a known real user
# (see `_DEV_USER_EMAIL`) so data created in dev is attributable to a person,
# not a synthetic placeholder.
#
# Defaults OFF: a misconfigured production deployment that forgets to set
# this fails safe (real auth required) rather than silently bypassing it.
#
# NEVER enable this in a production environment.
# ---------------------------------------------------------------------------
_BYPASS_AUTH = os.getenv("NCCRD_BYPASS_AUTH", "0") == "1"

#: Real user that all dev-bypass activity is attributed to.
_DEV_USER_EMAIL = "n.bingani@saeon.nrf.ac.za"
_DEV_USER_NAME = "N. Bingani"

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@dataclass
class Authorized:
    """An Authorized object represents a statement that the request carries
    a valid identity — either a real, verified JWT, or (in dev-bypass mode)
    the fixed dev user.

    ``internal_user_id`` is the resolved ``nccrd.user.id`` primary key —
    use this (not ``user_id`` / ``client_id``) wherever a FK-compatible
    user reference is needed (e.g. ``Submission.createdby``).
    """
    client_id: str
    user_id: Optional[str]
    internal_user_id: int


def generate_temp_password() -> str:
    return secrets.token_urlsafe(12)


def hash_password(plain: str) -> str:
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


def create_access_token(user: User) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=nccrd_config.NCCRD.JWT_EXPIRES_MINUTES)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "exp": expires_at,
    }
    return jwt.encode(payload, nccrd_config.NCCRD.JWT_SECRET, algorithm=nccrd_config.NCCRD.JWT_ALGORITHM)


def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            nccrd_config.NCCRD.JWT_SECRET,
            algorithms=[nccrd_config.NCCRD.JWT_ALGORITHM],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={'WWW-Authenticate': 'Bearer'},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={'WWW-Authenticate': 'Bearer'},
        )


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


def _authorize_request(request: Request, db: Session) -> Authorized:
    # Short-circuit for local development — no JWT required.
    if _BYPASS_AUTH:
        dev_user = _get_or_create_dev_user(db)
        return Authorized(client_id="dev-client", user_id=None, internal_user_id=dev_user.id)

    auth_header = request.headers.get('Authorization')
    scheme, token = get_authorization_scheme_param(auth_header)
    if not auth_header or scheme.lower() != 'bearer':
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            headers={'WWW-Authenticate': 'Bearer'},
        )

    claims = _decode_token(token)

    user = db.query(User).filter(User.id == int(claims["sub"])).first()
    if user is None or user.deleted:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            headers={'WWW-Authenticate': 'Bearer'},
        )

    return Authorized(client_id="nccrd-ui", user_id=str(user.id), internal_user_id=user.id)


class Authorize(HTTPBearer):
    """FastAPI dependency: resolves the caller's identity from a JWT bearer
    token (or the dev-bypass user), raising 401 if the request isn't
    authenticated. Fine-grained authorization is a separate concern, handled
    by ``RequirePermission``."""

    def __init__(self):
        super().__init__(auto_error=False, scheme_name='Bearer')

    async def __call__(self, request: Request, db: Session = Depends(get_db)) -> Authorized:
        return _authorize_request(request, db)
