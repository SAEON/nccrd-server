"""
API router for local JWT authentication: login and password changes.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN

from nccrd.api.lib.auth import Authorize, Authorized, create_access_token, hash_password, verify_password
from nccrd.api.models import ChangePasswordRequest, LoginRequest, RegisterRequest, TokenResponse
from nccrd.config import nccrd_config
from nccrd.db import get_db
from nccrd.db.models.rbac import User

router = APIRouter()

# Generic message for any failed login — deliberately identical whether the
# email is unknown or the password is wrong, to avoid leaking which emails
# are registered.
_INVALID_CREDENTIALS = "Invalid email or password."

#: Same reply whether or not the email already has an account, so the form
#: can't be used to find out who is registered.
_REGISTRATION_RECEIVED = (
    "Thanks. An administrator will review your request, and you can log in once it's approved. "
    "If you already have an account, log in instead."
)

#: What a self-registered account sees at login before it's approved.
_REGISTRATION_BLOCKED = {
    "pending": "Your account is waiting for an administrator's approval.",
    "rejected": "Your account request was not approved. Contact the NCCRD team if you think this is a mistake.",
}


def _find_user(db: Session, email: str):
    """Look up an account by email, ignoring case (no two accounts differ only by case)."""
    return db.query(User).filter(func.lower(User.email) == email.strip().lower(), User.deleted.isnot(True)).first()


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Exchange email + password for a JWT access token.",
)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = _find_user(db, body.email)

    if user is None or user.password_hash is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail=_INVALID_CREDENTIALS)
    # Only after a correct password, so this can't reveal which emails exist.
    if user.registration_status in _REGISTRATION_BLOCKED:
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail=_REGISTRATION_BLOCKED[user.registration_status])

    token = create_access_token(user)
    return TokenResponse(
        access_token=token,
        expires_in=nccrd_config.NCCRD.JWT_EXPIRES_MINUTES * 60,
        must_change_password=user.password_set_at is None,
    )


@router.post(
    "/register",
    status_code=202,
    summary="Request an account. An administrator approves it before it can log in.",
)
def register(body: RegisterRequest, db: Session = Depends(get_db)) -> dict:
    email = body.email.strip()
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        raise HTTPException(status_code=422, detail="Enter a valid email address.")
    if _find_user(db, email) is None:
        db.add(User(
            name=body.name.strip(),
            email=email,
            organisation=body.organisation.strip(),
            registration_note=(body.note or "").strip() or None,
            password_hash=hash_password(body.password),
            password_set_at=datetime.now(timezone.utc),
            registration_status="pending",
        ))
        db.commit()
    return {"detail": _REGISTRATION_RECEIVED}


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Exchange a still-valid access token for a fresh one.",
)
def refresh(
        db: Session = Depends(get_db),
        auth: Authorized = Depends(Authorize()),
) -> TokenResponse:
    """
    Lets an active session outlive the fixed token lifetime: the frontend
    calls this while the user is working, so nobody is logged out mid-capture.
    An expired or revoked token is rejected by ``Authorize`` like any request.
    """
    user = db.query(User).filter(User.id == auth.internal_user_id).first()
    return TokenResponse(
        access_token=create_access_token(user),
        expires_in=nccrd_config.NCCRD.JWT_EXPIRES_MINUTES * 60,
        must_change_password=user.password_set_at is None,
    )


@router.post(
    "/change-password",
    summary="Change the current user's password.",
)
def change_password(
        body: ChangePasswordRequest,
        db: Session = Depends(get_db),
        auth: Authorized = Depends(Authorize()),
) -> dict:
    user = db.query(User).filter(User.id == auth.internal_user_id).first()
    if user is None or user.password_hash is None or not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Current password is incorrect.")

    user.password_hash = hash_password(body.new_password)
    user.password_set_at = datetime.now(timezone.utc)
    db.commit()
    return {"detail": "Password updated."}
