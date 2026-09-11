"""
API router for local JWT authentication: login and password changes.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from starlette.status import HTTP_401_UNAUTHORIZED

from nccrd.api.lib.auth import Authorize, Authorized, create_access_token, hash_password, verify_password
from nccrd.api.models import ChangePasswordRequest, LoginRequest, TokenResponse
from nccrd.config import nccrd_config
from nccrd.db import get_db
from nccrd.db.models.rbac import User

router = APIRouter()

# Generic message for any failed login — deliberately identical whether the
# email is unknown or the password is wrong, to avoid leaking which emails
# are registered.
_INVALID_CREDENTIALS = "Invalid email or password."


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Exchange email + password for a JWT access token.",
)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.email == body.email, User.deleted.isnot(True)).first()

    if user is None or user.password_hash is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail=_INVALID_CREDENTIALS)

    token = create_access_token(user)
    return TokenResponse(
        access_token=token,
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
