"""Database engine, sessions and row-level-security (RLS) context.

Every transaction begins by setting two transaction-local GUCs that the RLS policies read:

    app.user_id    -> UUID of the authenticated subject whose rows may be touched ('' = none)
    app.privileged -> 'on' only for admin/system operations that were authorised in code first

Because `set_config(..., is_local => true)` resets at transaction end, the values are
re-applied in an `after_begin` hook, so a commit mid-request never drops the scope.
RLS is defence in depth: application code still checks ownership on every query.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from typing import Any

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

_SET_SCOPE = text("SELECT set_config('app.user_id', :uid, true), set_config('app.privileged', :priv, true)")


@lru_cache
def get_engine() -> Engine:
    s = get_settings()
    return create_engine(
        s.database_url.get_secret_value(),
        pool_size=s.db_pool_size,
        max_overflow=s.db_max_overflow,
        pool_timeout=s.db_pool_timeout_seconds,
        pool_pre_ping=True,
        pool_recycle=1800,
        connect_args={"application_name": "twinpath-api", "connect_timeout": 5},
    )


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


@event.listens_for(Session, "after_begin")
def _apply_rls_scope(session: Session, transaction: Any, connection: Any) -> None:
    uid = session.info.get("rls_user_id")
    connection.execute(
        _SET_SCOPE,
        {"uid": str(uid) if uid else "", "priv": "on" if session.info.get("rls_privileged") else "off"},
    )


def set_rls_subject(db: Session, user_id: uuid.UUID | None) -> None:
    """Scope the session to one data subject (the authenticated user, or a student whose
    data an authorised mentor/admin is reading)."""
    db.info["rls_user_id"] = user_id
    if db.in_transaction():
        db.execute(_SET_SCOPE, {"uid": str(user_id) if user_id else "", "priv": "on" if db.info.get("rls_privileged") else "off"})


@contextmanager
def privileged_scope(db: Session) -> Iterator[Session]:
    """Temporarily lift RLS for an operation that has ALREADY been authorised in code
    (admin catalogue management, retention jobs, assessor label writes)."""
    previous = db.info.get("rls_privileged", False)
    db.info["rls_privileged"] = True
    if db.in_transaction():
        db.execute(_SET_SCOPE, {"uid": str(db.info.get("rls_user_id") or ""), "priv": "on"})
    try:
        yield db
    finally:
        db.info["rls_privileged"] = previous
        if db.in_transaction():
            db.execute(_SET_SCOPE, {"uid": str(db.info.get("rls_user_id") or ""), "priv": "on" if previous else "off"})


def rowcount(result: Any) -> int:
    """Affected-row count of a DML result (typed helper for CursorResult.rowcount)."""
    return int(getattr(result, "rowcount", 0) or 0)


def get_db() -> Iterator[Session]:
    """Request-scoped session. Writes must `db.commit()` explicitly inside the endpoint/service
    so that a failed commit surfaces as an error response; anything left uncommitted here is
    rolled back (never silently committed after the response was produced)."""
    db = get_session_factory()()
    try:
        yield db
    finally:
        if db.in_transaction():
            db.rollback()
        db.close()


@contextmanager
def system_session() -> Iterator[Session]:
    """Session for CLI/background jobs. Privileged; use only for code paths that are not
    reachable from user requests."""
    db = get_session_factory()()
    db.info["rls_privileged"] = True
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
