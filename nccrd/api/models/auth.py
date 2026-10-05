"""
Pydantic v1 schemas for local JWT authentication.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str = Field(..., description="User's email address.")
    password: str = Field(..., description="User's password.")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Token lifetime in seconds.")
    must_change_password: bool = Field(
        False, description="True if the user must set a new password before continuing.",
    )


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., description="The user's current (or temporary) password.")
    new_password: str = Field(..., min_length=8, description="The new password to set.")


class RegisterRequest(BaseModel):
    """Self sign-up. The account can't log in until an admin approves it."""

    name: str = Field(..., min_length=1, max_length=500, description="Full name.")
    email: str = Field(..., min_length=3, max_length=500, description="Email address, used to log in.")
    organisation: str = Field(..., min_length=1, max_length=500, description="Organisation the person works for.")
    password: str = Field(..., min_length=8, description="At least 8 characters.")
    note: Optional[str] = Field(None, max_length=2000, description="Why they need an account (shown to the admin).")
