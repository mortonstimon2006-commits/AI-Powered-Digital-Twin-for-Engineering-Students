from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Request, Response, status
from sqlalchemy import select

from app.config import get_settings
from app.db import set_rls_subject
from app.deps import DB, CurrentUser, client_ip, client_ip_prefix
from app.models import StudentProfile, User
from app.schemas.auth import (
    ChangePasswordIn,
    ForgotPasswordIn,
    LoginIn,
    LoginOut,
    MeOut,
    MfaDisableIn,
    MfaLoginIn,
    MfaSetupOut,
    MfaVerifyIn,
    RegisterIn,
    ResetPasswordIn,
    SessionOut,
    TokenIn,
    UserOut,
)
from app.schemas.common import Message
from app.services import auth_service, email

router = APIRouter(prefix="/auth", tags=["auth"])

REGISTER_MESSAGE = (
    "If this email address can be registered, your account is ready. Check your inbox for a verification link, then sign in."
)
RESET_MESSAGE = "If an account exists for this address, a password reset link has been sent."


def _set_auth_cookies(response: Response, issued: auth_service.IssuedSession) -> None:
    s = get_settings()
    max_age = s.session_absolute_hours * 3600
    response.set_cookie(
        s.session_cookie_name, issued.token, max_age=max_age, httponly=True, secure=s.cookie_secure, samesite="lax", path="/"
    )
    # Readable by the SPA (double-submit); useless without the HttpOnly session cookie.
    response.set_cookie(
        s.csrf_cookie_name,
        issued.csrf_token,
        max_age=max_age,
        httponly=False,
        secure=s.cookie_secure,
        samesite="strict",
        path="/",
    )


def _clear_auth_cookies(response: Response) -> None:
    s = get_settings()
    response.delete_cookie(s.session_cookie_name, path="/", secure=s.cookie_secure, httponly=True, samesite="lax")
    response.delete_cookie(s.csrf_cookie_name, path="/", secure=s.cookie_secure, samesite="strict")


def user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        email_verified=user.email_verified_at is not None,
        mfa_enabled=user.mfa_enabled_at is not None,
        created_at=user.created_at,
    )


def _me(db: DB, user: User, csrf: str | None = None) -> MeOut:
    # Called right after login too, before the request is RLS-scoped: scope it to this (now
    # authenticated) user, otherwise the student's own profile row is invisible.
    set_rls_subject(db, user.id)
    onboarded = db.scalar(select(StudentProfile.onboarding_completed_at).where(StudentProfile.user_id == user.id))
    return MeOut(
        user=user_out(user),
        csrf_token=csrf,
        onboarding_completed=onboarded is not None or user.role != "student",
        email_verification_required=get_settings().require_email_verification and user.email_verified_at is None,
    )


@router.post("/register", status_code=status.HTTP_202_ACCEPTED, response_model=Message)
def register(body: RegisterIn, request: Request, db: DB, background: BackgroundTasks) -> Message:
    outcome = auth_service.register(
        db,
        email=str(body.email),
        password=body.password,
        display_name=body.display_name,
        consent=body.accept_profile_processing,
        ip=client_ip(request),
        ip_pref=client_ip_prefix(request),
    )
    # Emails are sent after the response so timing does not reveal whether the account existed.
    if outcome.created and outcome.verification_token:
        background.add_task(email.verification_email, outcome.email, outcome.verification_token)
    elif not outcome.created:
        background.add_task(email.account_exists_email, outcome.email)
    return Message(message=REGISTER_MESSAGE)


@router.post("/login", response_model=LoginOut)
def login(body: LoginIn, request: Request, response: Response, db: DB) -> LoginOut:
    result = auth_service.login(
        db,
        email=str(body.email),
        password=body.password,
        ip=client_ip(request),
        ip_pref=client_ip_prefix(request),
        user_agent=request.headers.get("user-agent"),
    )
    if result.mfa_challenge:
        return LoginOut(status="mfa_required", mfa_challenge=result.mfa_challenge)
    assert result.issued is not None
    _set_auth_cookies(response, result.issued)
    return LoginOut(status="authenticated", me=_me(db, result.user, result.issued.csrf_token))


@router.post("/login/mfa", response_model=LoginOut)
def login_mfa(body: MfaLoginIn, request: Request, response: Response, db: DB) -> LoginOut:
    result = auth_service.login_mfa(
        db,
        challenge=body.challenge,
        code=body.code,
        ip=client_ip(request),
        ip_pref=client_ip_prefix(request),
        user_agent=request.headers.get("user-agent"),
    )
    assert result.issued is not None
    _set_auth_cookies(response, result.issued)
    return LoginOut(status="authenticated", me=_me(db, result.user, result.issued.csrf_token))


@router.post("/logout", response_model=Message)
def logout(principal: CurrentUser, response: Response, db: DB) -> Message:
    auth_service.logout(db, principal.session)
    _clear_auth_cookies(response)
    return Message(message="Signed out.")


@router.get("/me", response_model=MeOut)
def me(principal: CurrentUser, db: DB) -> MeOut:
    return _me(db, principal.user)


@router.get("/csrf", response_model=MeOut)
def refresh_csrf(principal: CurrentUser, response: Response, db: DB) -> MeOut:
    """Re-issues the CSRF token for the current session (e.g. if the cookie was cleared)."""
    csrf = auth_service.rotate_csrf(db, principal.session)
    s = get_settings()
    response.set_cookie(
        s.csrf_cookie_name,
        csrf,
        max_age=s.session_absolute_hours * 3600,
        httponly=False,
        secure=s.cookie_secure,
        samesite="strict",
        path="/",
    )
    return _me(db, principal.user, csrf)


@router.get("/sessions", response_model=list[SessionOut])
def sessions(principal: CurrentUser, db: DB) -> list[SessionOut]:
    return [
        SessionOut(
            id=s.id,
            created_at=s.created_at,
            last_seen_at=s.last_seen_at,
            expires_at=s.expires_at,
            user_agent=s.user_agent,
            ip_prefix=s.ip_prefix,
            current=s.id == principal.session.id,
        )
        for s in auth_service.list_sessions(db, principal.id)
    ]


@router.delete("/sessions/{session_id}", response_model=Message)
def revoke_session(session_id: uuid.UUID, principal: CurrentUser, db: DB) -> Message:
    auth_service.revoke_session(db, principal.id, session_id)
    return Message(message="Session revoked.")


@router.post("/sessions/revoke-others", response_model=Message)
def revoke_other_sessions(principal: CurrentUser, db: DB) -> Message:
    n = auth_service.revoke_all_sessions(db, principal.id, except_session=principal.session.id)
    db.commit()
    return Message(message=f"Signed out of {n} other session(s).")


@router.post("/password/change", response_model=Message)
def change_password(
    body: ChangePasswordIn, request: Request, principal: CurrentUser, db: DB, background: BackgroundTasks
) -> Message:
    auth_service.change_password(
        db,
        principal.user,
        principal.session,
        current=body.current_password,
        new=body.new_password,
        ip_pref=client_ip_prefix(request),
    )
    background.add_task(email.password_changed_email, principal.user.email)
    return Message(message="Password changed. Other sessions were signed out.")


@router.post("/password/forgot", status_code=status.HTTP_202_ACCEPTED, response_model=Message)
def forgot_password(body: ForgotPasswordIn, request: Request, db: DB, background: BackgroundTasks) -> Message:
    result = auth_service.request_password_reset(
        db, email=str(body.email), ip=client_ip(request), ip_pref=client_ip_prefix(request)
    )
    if result is not None:
        background.add_task(email.password_reset_email, *result)
    return Message(message=RESET_MESSAGE)


@router.post("/password/reset", response_model=Message)
def reset_password(body: ResetPasswordIn, request: Request, db: DB, background: BackgroundTasks) -> Message:
    addr = auth_service.reset_password(
        db, raw_token=body.token, new_password=body.new_password, ip=client_ip(request), ip_pref=client_ip_prefix(request)
    )
    background.add_task(email.password_changed_email, addr)
    return Message(message="Password updated. Please sign in with your new password.")


@router.post("/email/verify", response_model=Message)
def verify_email(body: TokenIn, request: Request, db: DB) -> Message:
    auth_service.verify_email(db, body.token, client_ip(request))
    return Message(message="Email address verified.")


@router.post("/email/resend", response_model=Message)
def resend_verification(principal: CurrentUser, db: DB, background: BackgroundTasks) -> Message:
    token = auth_service.new_verification_token(db, principal.user)
    if token:
        background.add_task(email.verification_email, principal.user.email, token)
    return Message(message="If your address is unverified, a new verification link has been sent.")


@router.post("/mfa/setup", response_model=MfaSetupOut)
def mfa_setup(principal: CurrentUser, db: DB) -> MfaSetupOut:
    secret, uri = auth_service.mfa_begin_setup(db, principal.user)
    return MfaSetupOut(secret=secret, otpauth_uri=uri)


@router.post("/mfa/verify", response_model=Message)
def mfa_verify(body: MfaVerifyIn, principal: CurrentUser, db: DB) -> Message:
    auth_service.mfa_confirm(db, principal.user, body.code)
    return Message(message="Two-factor authentication enabled.")


@router.post("/mfa/disable", response_model=Message)
def mfa_disable(body: MfaDisableIn, principal: CurrentUser, db: DB) -> Message:
    auth_service.mfa_disable(db, principal.user, password=body.password, code=body.code)
    return Message(message="Two-factor authentication disabled.")
