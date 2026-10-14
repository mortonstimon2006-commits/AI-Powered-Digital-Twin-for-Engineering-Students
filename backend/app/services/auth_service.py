"""Authentication, sessions, account recovery and TOTP MFA.

Design: opaque server-side sessions in an HttpOnly, SameSite=Lax, Secure cookie
(`__Host-` prefixed outside local HTTP dev), plus a per-session synchroniser CSRF token
that the SPA echoes in `X-CSRF-Token`. No JWTs; revocation is immediate.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pyotp
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import set_rls_subject
from app.errors import AppError, Forbidden, NotFound, Unauthorized
from app.models import AuthToken, Consent, StudentProfile, User, UserSession
from app.security import crypto
from app.security.passwords import hash_password, needs_rehash, password_problems, verify_password
from app.security.ratelimit import (
    LOGIN_ACCOUNT,
    LOGIN_IP,
    REGISTER_IP,
    RESET_REQUEST_ACCOUNT,
    RESET_REQUEST_IP,
    TOKEN_REDEEM_IP,
    limiter,
)
from app.security.tokens import digest, new_token
from app.services import audit

POLICY_VERSION = "2026-10"
GENERIC_LOGIN_ERROR = "Invalid email or password, or too many recent attempts. Please try again later."
LOCKOUT_THRESHOLD = 5
VERIFY_TTL = timedelta(hours=24)
RESET_TTL = timedelta(minutes=30)
MFA_CHALLENGE_TTL = timedelta(minutes=5)
MFA_ISSUER = "TwinPath AI"


def _now() -> datetime:
    return datetime.now(UTC)


def _require_strong(password: str, email: str, display_name: str | None) -> None:
    problems = password_problems(password, email=email, display_name=display_name)
    if problems:
        raise AppError("The password does not meet the requirements.", code="weak_password", details=problems, status_code=422)


def _issue_token(db: Session, user_id: uuid.UUID, purpose: str, ttl: timedelta) -> str:
    raw = new_token()
    db.add(AuthToken(user_id=user_id, purpose=purpose, token_hash=digest(raw), expires_at=_now() + ttl))
    return raw


def _redeem_token(db: Session, raw: str, purpose: str) -> AuthToken:
    tok = db.scalar(select(AuthToken).where(AuthToken.token_hash == digest(raw), AuthToken.purpose == purpose).with_for_update())
    if tok is None or tok.used_at is not None or tok.expires_at <= _now() or tok.attempts >= 5:
        raise AppError("This link is invalid or has expired.", code="token_invalid")
    return tok


# ----------------------------------------------------------------------------- registration


@dataclass
class RegistrationOutcome:
    """Never returned to the client verbatim — the API answers identically either way."""

    created: bool
    email: str
    verification_token: str | None


def register(
    db: Session, *, email: str, password: str, display_name: str, consent: bool, ip: str | None, ip_pref: str | None
) -> RegistrationOutcome:
    limiter.hit(REGISTER_IP, ip or "unknown")
    email = email.lower()
    if not consent:
        raise AppError(
            "Consent to process your profile data is required to use TwinPath AI.", code="consent_required", status_code=422
        )
    _require_strong(password, email, display_name)
    pw_hash = hash_password(password)  # hash before the lookup: equal work for both branches

    if db.scalar(select(User.id).where(User.email == email)) is not None:
        audit.record(db, "auth.register", actor_id=None, outcome="failure", ip_prefix=ip_pref, details={"reason": "email_in_use"})
        db.commit()
        return RegistrationOutcome(created=False, email=email, verification_token=None)

    user = User(email=email, password_hash=pw_hash, display_name=display_name, role="student")
    db.add(user)
    db.flush()
    set_rls_subject(db, user.id)
    db.add(Consent(user_id=user.id, purpose="profile_processing", granted=True, policy_version=POLICY_VERSION))
    db.add(StudentProfile(user_id=user.id))
    token = _issue_token(db, user.id, "verify_email", VERIFY_TTL)
    audit.record(db, "auth.register", actor_id=user.id, target_type="user", target_id=user.id, ip_prefix=ip_pref)
    db.commit()
    return RegistrationOutcome(created=True, email=email, verification_token=token)


def verify_email(db: Session, raw: str, ip: str | None) -> None:
    limiter.hit(TOKEN_REDEEM_IP, ip or "unknown")
    tok = _redeem_token(db, raw, "verify_email")
    tok.used_at = _now()
    user = db.get(User, tok.user_id)
    if user is None:
        raise NotFound("Account not found.")
    if user.email_verified_at is None:
        user.email_verified_at = _now()
    audit.record(db, "auth.email_verified", actor_id=user.id, target_type="user", target_id=user.id)
    db.commit()


def new_verification_token(db: Session, user: User) -> str | None:
    if user.email_verified_at is not None:
        return None
    db.execute(
        update(AuthToken)
        .where(AuthToken.user_id == user.id, AuthToken.purpose == "verify_email", AuthToken.used_at.is_(None))
        .values(used_at=_now())
    )
    token = _issue_token(db, user.id, "verify_email", VERIFY_TTL)
    db.commit()
    return token


# ----------------------------------------------------------------------------- login / sessions


@dataclass
class IssuedSession:
    token: str
    csrf_token: str
    session: UserSession


def create_session(db: Session, user: User, *, user_agent: str | None, ip_pref: str | None) -> IssuedSession:
    s = get_settings()
    raw, csrf = new_token(), new_token()
    sess = UserSession(
        user_id=user.id,
        token_hash=digest(raw),
        csrf_hash=digest(csrf),
        expires_at=_now() + timedelta(hours=s.session_absolute_hours),
        user_agent=(user_agent or "")[:200] or None,
        ip_prefix=ip_pref,
    )
    db.add(sess)
    db.flush()
    return IssuedSession(token=raw, csrf_token=csrf, session=sess)


def rotate_csrf(db: Session, sess: UserSession) -> str:
    csrf = new_token()
    sess.csrf_hash = digest(csrf)
    db.commit()
    return csrf


@dataclass
class LoginResult:
    user: User
    issued: IssuedSession | None = None
    mfa_challenge: str | None = None


def login(db: Session, *, email: str, password: str, ip: str | None, ip_pref: str | None, user_agent: str | None) -> LoginResult:
    email = email.lower()
    limiter.hit(LOGIN_IP, ip or "unknown")
    limiter.hit(LOGIN_ACCOUNT, email)
    now = _now()
    # FOR NO KEY UPDATE: serialises concurrent attempts on the counter without blocking the
    # FK KEY SHARE lock that the standalone audit insert needs.
    user = db.scalar(select(User).where(User.email == email).with_for_update(key_share=True))

    if user is not None and user.locked_until is not None and user.locked_until > now:
        verify_password(None, password)  # equalise timing
        db.rollback()
        audit.record_standalone("auth.login", actor_id=user.id, outcome="denied", ip_prefix=ip_pref, details={"reason": "locked"})
        raise Unauthorized(GENERIC_LOGIN_ERROR, code="invalid_credentials")

    ok = verify_password(user.password_hash if user else None, password)
    if user is None or not ok or not user.is_active:
        if user is not None:
            user.failed_login_count += 1
            if user.failed_login_count >= LOCKOUT_THRESHOLD:
                # Exponential back-off: 15 min, 30 min, 60 min ... capped at 24 h.
                exponent = min(user.failed_login_count - LOCKOUT_THRESHOLD, 7)
                user.locked_until = now + min(timedelta(minutes=15 * 2**exponent), timedelta(hours=24))
            db.commit()
        audit.record_standalone(
            "auth.login",
            actor_id=user.id if user else None,
            outcome="failure",
            ip_prefix=ip_pref,
            details={"reason": "bad_credentials"},
        )
        raise Unauthorized(GENERIC_LOGIN_ERROR, code="invalid_credentials")

    if get_settings().require_email_verification and user.email_verified_at is None:
        db.rollback()
        raise Forbidden("Please verify your email address before signing in.", code="email_unverified")

    user.failed_login_count = 0
    user.locked_until = None
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)

    if user.mfa_enabled_at is not None:
        challenge = _issue_token(db, user.id, "mfa_challenge", MFA_CHALLENGE_TTL)
        audit.record(db, "auth.login.mfa_challenge", actor_id=user.id, ip_prefix=ip_pref)
        db.commit()
        return LoginResult(user=user, mfa_challenge=challenge)

    user.last_login_at = now
    issued = create_session(db, user, user_agent=user_agent, ip_pref=ip_pref)
    audit.record(db, "auth.login", actor_id=user.id, ip_prefix=ip_pref)
    db.commit()
    return LoginResult(user=user, issued=issued)


def login_mfa(
    db: Session, *, challenge: str, code: str, ip: str | None, ip_pref: str | None, user_agent: str | None
) -> LoginResult:
    limiter.hit(TOKEN_REDEEM_IP, ip or "unknown")
    tok = _redeem_token(db, challenge, "mfa_challenge")
    user = db.get(User, tok.user_id)
    secret = crypto.decrypt(user.mfa_secret_encrypted) if user and user.mfa_secret_encrypted else None
    if user is None or secret is None or not user.is_active:
        raise Unauthorized(GENERIC_LOGIN_ERROR, code="invalid_credentials")
    if not pyotp.TOTP(secret).verify(code, valid_window=1):
        tok.attempts += 1
        db.commit()
        audit.record_standalone("auth.login.mfa", actor_id=user.id, outcome="failure", ip_prefix=ip_pref)
        raise Unauthorized("The verification code is incorrect.", code="mfa_invalid")
    tok.used_at = _now()
    user.last_login_at = _now()
    issued = create_session(db, user, user_agent=user_agent, ip_pref=ip_pref)
    audit.record(db, "auth.login", actor_id=user.id, ip_prefix=ip_pref, details={"mfa": True})
    db.commit()
    return LoginResult(user=user, issued=issued)


def logout(db: Session, sess: UserSession) -> None:
    sess.revoked_at = _now()
    audit.record(db, "auth.logout", actor_id=sess.user_id)
    db.commit()


def list_sessions(db: Session, user_id: uuid.UUID) -> list[UserSession]:
    return list(
        db.scalars(
            select(UserSession)
            .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None), UserSession.expires_at > _now())
            .order_by(UserSession.last_seen_at.desc())
        )
    )


def revoke_session(db: Session, user_id: uuid.UUID, session_id: uuid.UUID) -> None:
    sess = db.scalar(select(UserSession).where(UserSession.id == session_id, UserSession.user_id == user_id))
    if sess is None or sess.revoked_at is not None:
        raise NotFound("Session not found.")
    sess.revoked_at = _now()
    audit.record(db, "auth.session.revoke", actor_id=user_id, target_type="session", target_id=session_id)
    db.commit()


def revoke_all_sessions(db: Session, user_id: uuid.UUID, *, except_session: uuid.UUID | None = None) -> int:
    stmt = update(UserSession).where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
    if except_session is not None:
        stmt = stmt.where(UserSession.id != except_session)
    result = db.execute(stmt.values(revoked_at=_now()))
    return int(result.rowcount or 0)  # type: ignore[attr-defined]


# ----------------------------------------------------------------------------- passwords


def change_password(
    db: Session, user: User, current_session: UserSession, *, current: str, new: str, ip_pref: str | None
) -> None:
    if not verify_password(user.password_hash, current):
        audit.record_standalone("auth.password.change", actor_id=user.id, outcome="failure", ip_prefix=ip_pref)
        raise AppError("The current password is incorrect.", code="invalid_password", status_code=400)
    _require_strong(new, user.email, user.display_name)
    if verify_password(user.password_hash, new):
        raise AppError("Choose a password different from the current one.", code="password_reused", status_code=422)
    user.password_hash = hash_password(new)
    user.password_changed_at = _now()
    revoked = revoke_all_sessions(db, user.id, except_session=current_session.id)
    audit.record(db, "auth.password.change", actor_id=user.id, ip_prefix=ip_pref, details={"sessions_revoked": revoked})
    db.commit()


def request_password_reset(db: Session, *, email: str, ip: str | None, ip_pref: str | None) -> tuple[str, str] | None:
    """Returns (email, token) when an email should be sent; the API response is identical
    either way so account existence is not disclosed."""
    email = email.lower()
    limiter.hit(RESET_REQUEST_IP, ip or "unknown")
    limiter.hit(RESET_REQUEST_ACCOUNT, email)
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not user.is_active:
        return None
    db.execute(
        update(AuthToken)
        .where(AuthToken.user_id == user.id, AuthToken.purpose == "reset_password", AuthToken.used_at.is_(None))
        .values(used_at=_now())
    )
    token = _issue_token(db, user.id, "reset_password", RESET_TTL)
    audit.record(db, "auth.password.reset_requested", actor_id=user.id, ip_prefix=ip_pref)
    db.commit()
    return email, token


def reset_password(db: Session, *, raw_token: str, new_password: str, ip: str | None, ip_pref: str | None) -> str:
    limiter.hit(TOKEN_REDEEM_IP, ip or "unknown")
    tok = _redeem_token(db, raw_token, "reset_password")
    user = db.get(User, tok.user_id)
    if user is None:
        raise AppError("This link is invalid or has expired.", code="token_invalid")
    _require_strong(new_password, user.email, user.display_name)
    tok.used_at = _now()
    user.password_hash = hash_password(new_password)
    user.password_changed_at = _now()
    user.failed_login_count = 0
    user.locked_until = None
    revoked = revoke_all_sessions(db, user.id)
    audit.record(db, "auth.password.reset", actor_id=user.id, ip_prefix=ip_pref, details={"sessions_revoked": revoked})
    db.commit()
    return user.email


# ----------------------------------------------------------------------------- MFA


def mfa_begin_setup(db: Session, user: User) -> tuple[str, str]:
    if user.mfa_enabled_at is not None:
        raise AppError("Two-factor authentication is already enabled.", code="mfa_already_enabled", status_code=409)
    secret = pyotp.random_base32()
    user.mfa_secret_encrypted = crypto.encrypt(secret)
    db.commit()
    uri = pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name=MFA_ISSUER)
    return secret, uri


def mfa_confirm(db: Session, user: User, code: str) -> None:
    secret = crypto.decrypt(user.mfa_secret_encrypted) if user.mfa_secret_encrypted else None
    if secret is None:
        raise AppError("Start two-factor setup first.", code="mfa_not_started", status_code=409)
    if not pyotp.TOTP(secret).verify(code, valid_window=1):
        raise AppError("The verification code is incorrect.", code="mfa_invalid", status_code=400)
    user.mfa_enabled_at = _now()
    audit.record(db, "auth.mfa.enabled", actor_id=user.id)
    db.commit()


def mfa_disable(db: Session, user: User, *, password: str, code: str) -> None:
    secret = crypto.decrypt(user.mfa_secret_encrypted) if user.mfa_secret_encrypted else None
    if user.mfa_enabled_at is None or secret is None:
        raise AppError("Two-factor authentication is not enabled.", code="mfa_not_enabled", status_code=409)
    if not verify_password(user.password_hash, password) or not pyotp.TOTP(secret).verify(code, valid_window=1):
        audit.record_standalone("auth.mfa.disable", actor_id=user.id, outcome="failure")
        raise AppError("Password or verification code is incorrect.", code="invalid_credentials", status_code=400)
    user.mfa_enabled_at = None
    user.mfa_secret_encrypted = None
    audit.record(db, "auth.mfa.disabled", actor_id=user.id)
    db.commit()
