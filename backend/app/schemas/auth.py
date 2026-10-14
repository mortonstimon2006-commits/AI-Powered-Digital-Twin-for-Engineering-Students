from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import EmailStr, Field, field_validator

from app.schemas.common import ApiModel, StrictModel


class RegisterIn(StrictModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)
    display_name: str = Field(min_length=2, max_length=80)
    accept_profile_processing: bool = Field(
        description="Consent to process the profile data the student enters (required to use the service)."
    )

    @field_validator("display_name")
    @classmethod
    def _printable(cls, v: str) -> str:
        if any(ord(c) < 32 for c in v):
            raise ValueError("contains control characters")
        return v


class LoginIn(StrictModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class MfaLoginIn(StrictModel):
    challenge: str = Field(min_length=20, max_length=128)
    code: str = Field(pattern=r"^\d{6}$")


class TokenIn(StrictModel):
    token: str = Field(min_length=20, max_length=128)


class ForgotPasswordIn(StrictModel):
    email: EmailStr


class ResetPasswordIn(StrictModel):
    token: str = Field(min_length=20, max_length=128)
    new_password: str = Field(min_length=1, max_length=256)


class ChangePasswordIn(StrictModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)


class MfaVerifyIn(StrictModel):
    code: str = Field(pattern=r"^\d{6}$")


class MfaDisableIn(StrictModel):
    password: str = Field(min_length=1, max_length=256)
    code: str = Field(pattern=r"^\d{6}$")


class UserOut(ApiModel):
    id: uuid.UUID
    email: str
    display_name: str
    role: Literal["student", "mentor", "admin"]
    email_verified: bool
    mfa_enabled: bool
    created_at: datetime


class MeOut(ApiModel):
    user: UserOut
    csrf_token: str | None = None
    onboarding_completed: bool
    email_verification_required: bool


class LoginOut(ApiModel):
    status: Literal["authenticated", "mfa_required"]
    mfa_challenge: str | None = None
    me: MeOut | None = None


class SessionOut(ApiModel):
    id: uuid.UUID
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    user_agent: str | None
    ip_prefix: str | None
    current: bool


class MfaSetupOut(ApiModel):
    secret: str
    otpauth_uri: str
