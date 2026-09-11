"""
Pydantic v1 schemas for local JWT authentication.
"""

from __future__ import annotations

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
