import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer
from fastapi.security.utils import get_authorization_scheme_param
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

#: bcrypt only uses the first 72 bytes of a password. passlib, used before,
#: truncated longer ones silently; newer bcrypt releases reject them instead,
#: so truncating here keeps every existing hash verifiable.
_BCRYPT_MAX_BYTES = 72


def _secret(plain: str) -> bytes:
    return plain.encode("utf-8")[:_BCRYPT_MAX_BYTES]


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
    """bcrypt, 12 rounds, $2b$: the same hashes passlib produced."""
    return bcrypt.hashpw(_secret(plain), bcrypt.gensalt(rounds=12)).decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_secret(plain), hashed.encode("ascii"))
    except ValueError:  # not a bcrypt hash
        return False


def create_access_token(user: User) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=nccrd_config.NCCRD.JWT_EXPIRES_MINUTES)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "exp": expires_at,
    }
    return jwt.encode(payload, nccrd_config.NCCRD.JWT_SECRET, algorithm=nccrd_config.NCCRD.JWT_ALGORITHM)


#: How long a password reset link works.
PASSWORD_RESET_MINUTES = 60
_PASSWORD_RESET = "password-reset"

#: Self-registered accounts that can't log in, so can't reset a password either.
BLOCKED_REGISTRATIONS = ("pending", "rejected")


def _password_reset_key(user: User) -> str:
    """
    Signs a reset link with the account's current password hash as well as
    the secret, so a link stops working once it is used (bcrypt salts every
    hash) and can never pass as an access token, or the other way round.
    """
    return f"{nccrd_config.NCCRD.JWT_SECRET}:{_PASSWORD_RESET}:{user.password_hash or ''}"


def create_password_reset_token(user: User) -> str:
    payload = {
        "sub": str(user.id),
        "purpose": _PASSWORD_RESET,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=PASSWORD_RESET_MINUTES),
    }
    return jwt.encode(payload, _password_reset_key(user), algorithm=nccrd_config.NCCRD.JWT_ALGORITHM)


def user_of_password_reset_token(db: Session, token: str) -> Optional[User]:
    """The account a reset link is for, or None if it is invalid, expired or already used."""
    try:
        # Only to find whose key to check the signature with.
        user_id = int(jwt.decode(token, options={"verify_signature": False})["sub"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        return None
    user = db.query(User).filter(User.id == user_id).first()
    if user is None or user.deleted or user.registration_status in BLOCKED_REGISTRATIONS:
        return None
    try:
        claims = jwt.decode(token, _password_reset_key(user), algorithms=[nccrd_config.NCCRD.JWT_ALGORITHM])
    except jwt.InvalidTokenError:
        return None
    return user if claims.get("purpose") == _PASSWORD_RESET else None


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
    # Self-registered accounts can't act until approved (login refuses them
    # too; this also covers a token issued before a request was rejected).
    if user is None or user.deleted or user.registration_status in BLOCKED_REGISTRATIONS:
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


class OptionalAuthorize(HTTPBearer):
    """FastAPI dependency for public endpoints that behave differently for a
    logged-in caller: resolves the identity when a valid token is sent, and
    returns None (instead of raising 401) for anonymous or invalid requests."""

    def __init__(self):
        super().__init__(auto_error=False, scheme_name='Bearer')

    async def __call__(self, request: Request, db: Session = Depends(get_db)) -> Optional[Authorized]:
        try:
            return _authorize_request(request, db)
        except HTTPException:
            return None
