"""
API router for local JWT authentication: login and password changes.
"""

import logging
import time
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.status import HTTP_400_BAD_REQUEST, HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN

from nccrd.api.lib.auth import (
    BLOCKED_REGISTRATIONS,
    PASSWORD_RESET_MINUTES,
    Authorize,
    Authorized,
    create_access_token,
    create_password_reset_token,
    hash_password,
    user_of_password_reset_token,
    verify_password,
)
from nccrd.api.lib.mail import send_mail
from nccrd.api.lib.tenant import get_current_tenant, site_address, site_name
from nccrd.api.models import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
)
from nccrd.config import nccrd_config
from nccrd.db import get_db
from nccrd.db.models.rbac import Tenant, User

logger = logging.getLogger(__name__)

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
    if not body.accept_privacy_notice:
        raise HTTPException(status_code=422, detail="Accept the privacy notice to request an account.")
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
            privacy_notice_accepted_at=datetime.now(timezone.utc),
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


#: Same reply whether or not the email has an account (see _REGISTRATION_RECEIVED).
_RESET_LINK_SENT = (
    "If an account uses that email address, we've sent it a link to set a new password. "
    f"The link works for {PASSWORD_RESET_MINUTES} minutes. Check your spam folder if it doesn't arrive."
)

#: At most one reset email per account in this many seconds, so the form
#: can't be used to flood someone's inbox. Kept in memory, so per API worker
#: process (4 in the container): enough to stop a flood, not an exact count.
_RESET_MAIL_INTERVAL = 60
_last_reset_mail = {}


def _reset_mail_allowed(user_id: int) -> bool:
    now = time.monotonic()
    if now - _last_reset_mail.get(user_id, -_RESET_MAIL_INTERVAL) < _RESET_MAIL_INTERVAL:
        return False
    _last_reset_mail[user_id] = now
    return True


@router.post(
    "/forgot-password",
    status_code=202,
    summary="Email a link to set a new password.",
)
def forgot_password(
        body: ForgotPasswordRequest,
        request: Request,
        background: BackgroundTasks,
        db: Session = Depends(get_db),
        tenant: Tenant = Depends(get_current_tenant),
) -> dict:
    """
    The link goes to the site the request came from (e.g. /mpumalanga). The
    reply never says whether the email has an account, and the email is sent
    after the reply, so its timing doesn't tell either.
    """
    user = _find_user(db, body.email)
    if user is None or user.registration_status in BLOCKED_REGISTRATIONS or not _reset_mail_allowed(user.id):
        return {"detail": _RESET_LINK_SENT}

    address = site_address(request, tenant)
    if address is None:
        logger.error("No password reset link was sent: set NCCRD_UI_URL to the site's address.")
        return {"detail": _RESET_LINK_SENT}

    name = site_name(tenant)
    # In the fragment, so the token never reaches a server log or a Referer header.
    link = f"{address}/reset-password#token={create_password_reset_token(user)}"
    background.add_task(
        send_mail,
        user.email,
        f"Set a new password for {name}",
        f"Hello {user.name},\n\n"
        f"Someone asked to set a new password for your {name} account ({user.email}).\n"
        f"To choose one, open this link within {PASSWORD_RESET_MINUTES} minutes:\n\n"
        f"{link}\n\n"
        "If you didn't ask for this, ignore this email: your password stays as it is.\n\n"
        f"{tenant.title or name}\n",
        sender_name=name,
    )
    return {"detail": _RESET_LINK_SENT}


@router.post(
    "/reset-password",
    summary="Set a new password with the token from an emailed link.",
)
def reset_password(body: ResetPasswordRequest, db: Session = Depends(get_db)) -> dict:
    user = user_of_password_reset_token(db, body.token)
    if user is None:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail="This link has expired or has already been used. Ask for a new one.",
        )
    user.password_hash = hash_password(body.new_password)
    user.password_set_at = datetime.now(timezone.utc)
    db.commit()
    return {"detail": "Your password is set. You can log in with it now."}
