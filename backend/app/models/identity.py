"""Accounts, sessions, one-time tokens, consent, mentor assignments and the audit trail."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_col, updated_at_col, uuid_pk

USER_ROLES = ("student", "mentor", "admin")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('student','mentor','admin')", name="role_valid"),
        CheckConstraint("email = lower(email)", name="email_lowercase"),
        CheckConstraint("failed_login_count >= 0", name="failed_login_nonneg"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False, server_default="student")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # TOTP secret, Fernet-encrypted with FIELD_ENCRYPTION_KEY (key held outside the DB).
    mfa_secret_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary)
    mfa_enabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_login_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    password_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class UserSession(Base):
    """Server-side browser session. Only SHA-256 digests of the bearer token and CSRF token
    are stored, so a database leak does not yield usable session credentials."""

    __tablename__ = "user_sessions"
    __table_args__ = (Index("ix_user_sessions_user_active", "user_id", "revoked_at"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[bytes] = mapped_column(LargeBinary(32), unique=True, nullable=False)
    csrf_hash: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    created_at: Mapped[datetime] = created_at_col()
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user_agent: Mapped[str | None] = mapped_column(String(200))
    ip_prefix: Mapped[str | None] = mapped_column(String(64))


class AuthToken(Base):
    """Single-use, expiring tokens (email verification, password reset, MFA challenge).
    Only the SHA-256 digest is persisted."""

    __tablename__ = "auth_tokens"
    __table_args__ = (
        CheckConstraint("purpose IN ('verify_email','reset_password','mfa_challenge')", name="purpose_valid"),
        Index("ix_auth_tokens_user_purpose", "user_id", "purpose"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    purpose: Mapped[str] = mapped_column(String(24), nullable=False)
    token_hash: Mapped[bytes] = mapped_column(LargeBinary(32), unique=True, nullable=False)
    created_at: Mapped[datetime] = created_at_col()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")


CONSENT_PURPOSES = ("profile_processing", "mentor_sharing", "research_use", "attendance_data")


class Consent(Base):
    __tablename__ = "consents"
    __table_args__ = (
        CheckConstraint(
            "purpose IN ('profile_processing','mentor_sharing','research_use','attendance_data')",
            name="purpose_valid",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    purpose: Mapped[str] = mapped_column(String(32), primary_key=True)
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    policy_version: Mapped[str] = mapped_column(String(16), nullable=False)
    updated_at: Mapped[datetime] = updated_at_col()


class MentorLink(Base):
    """Admin-assigned mentor↔student relation. A mentor sees a student's twin only when this
    link exists AND the student has granted the `mentor_sharing` consent."""

    __tablename__ = "mentor_links"
    __table_args__ = (CheckConstraint("mentor_id <> student_id", name="not_self"),)

    mentor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    created_at: Mapped[datetime] = created_at_col()
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))


class AuditEvent(Base):
    """Append-only security/audit trail (the app role has no UPDATE/DELETE on this table)."""

    __tablename__ = "audit_events"
    __table_args__ = (
        CheckConstraint("outcome IN ('success','failure','denied')", name="outcome_valid"),
        Index("ix_audit_actor_time", "actor_id", "occurred_at"),
        Index("ix_audit_action_time", "action", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    occurred_at: Mapped[datetime] = created_at_col()
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False, server_default="success")
    target_type: Mapped[str | None] = mapped_column(String(32))
    target_id: Mapped[str | None] = mapped_column(String(64))
    ip_prefix: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
