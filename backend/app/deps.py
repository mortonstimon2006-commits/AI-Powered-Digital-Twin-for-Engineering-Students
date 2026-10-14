"""FastAPI dependencies: authenticated principal, CSRF verification, role checks."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db, set_rls_subject
from app.errors import Forbidden, Unauthorized
from app.middleware import UNSAFE_METHODS
from app.models import User, UserSession
from app.security.tokens import constant_time_equals, digest, ip_prefix

LAST_SEEN_RESOLUTION = timedelta(minutes=5)


@dataclass
class Principal:
    user: User
    session: UserSession

    @property
    def id(self) -> uuid.UUID:
        return self.user.id

    @property
    def role(self) -> str:
        return self.user.role


def client_ip(request: Request) -> str | None:
    if get_settings().trust_proxy_headers:
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


def client_ip_prefix(request: Request) -> str | None:
    return ip_prefix(client_ip(request))


def _load_session(request: Request, db: Session) -> Principal | None:
    settings = get_settings()
    raw = request.cookies.get(settings.session_cookie_name)
    if not raw or len(raw) > 128:
        return None
    now = datetime.now(UTC)
    row = db.execute(
        select(UserSession, User)
        .join(User, User.id == UserSession.user_id)
        .where(UserSession.token_hash == digest(raw), UserSession.revoked_at.is_(None))
    ).first()
    if row is None:
        return None
    sess, user = row
    idle_limit = timedelta(hours=settings.session_idle_hours)
    if sess.expires_at <= now or now - sess.last_seen_at > idle_limit or not user.is_active:
        return None
    if now - sess.last_seen_at > LAST_SEEN_RESOLUTION:
        sess.last_seen_at = now
        db.commit()
    return Principal(user=user, session=sess)


def _verify_csrf(request: Request, principal: Principal) -> None:
    token = request.headers.get("x-csrf-token", "")
    if not token or len(token) > 128 or not constant_time_equals(digest(token), principal.session.csrf_hash):
        raise Forbidden("Invalid or missing CSRF token.", code="csrf_invalid")


def get_principal(request: Request, db: Annotated[Session, Depends(get_db)]) -> Principal:
    principal = _load_session(request, db)
    if principal is None:
        raise Unauthorized("Please sign in to continue.")
    if request.method in UNSAFE_METHODS:
        _verify_csrf(request, principal)
    # Every subsequent query in this request is RLS-scoped to the authenticated user.
    set_rls_subject(db, principal.user.id)
    return principal


def get_optional_principal(request: Request, db: Annotated[Session, Depends(get_db)]) -> Principal | None:
    principal = _load_session(request, db)
    if principal is not None:
        set_rls_subject(db, principal.user.id)
    return principal


def require_roles(*roles: str):
    def _dep(principal: Annotated[Principal, Depends(get_principal)]) -> Principal:
        if principal.user.role not in roles:
            raise Forbidden("You do not have permission to perform this action.")
        return principal

    return _dep


CurrentUser = Annotated[Principal, Depends(get_principal)]
OptionalUser = Annotated[Principal | None, Depends(get_optional_principal)]
DB = Annotated[Session, Depends(get_db)]
AdminUser = Annotated[Principal, Depends(require_roles("admin"))]
StaffUser = Annotated[Principal, Depends(require_roles("mentor", "admin"))]
