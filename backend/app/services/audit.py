"""Audit trail for security-relevant and sensitive actions. Details are redacted; no
credentials, document text or chat content is ever written here."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.logging_config import redact
from app.models import AuditEvent

log = logging.getLogger("twinpath.audit")


def record(
    db: Session,
    action: str,
    *,
    actor_id: uuid.UUID | None,
    outcome: str = "success",
    target_type: str | None = None,
    target_id: str | int | uuid.UUID | None = None,
    ip_prefix: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Adds the event to the current transaction (committed with the action it describes)."""
    db.add(
        AuditEvent(
            actor_id=actor_id,
            action=action,
            outcome=outcome,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            ip_prefix=ip_prefix,
            details=redact(details) if details else None,
        )
    )
    log.info("audit", extra={"ctx": {"action": action, "outcome": outcome, "target_type": target_type}})


def record_standalone(action: str, **kwargs: Any) -> None:
    """For failures where the request transaction will be rolled back (e.g. failed login):
    write the audit row in its own short transaction so the evidence survives."""
    from app.db import get_session_factory

    db = get_session_factory()()
    try:
        record(db, action, **kwargs)
        db.commit()
    except Exception:  # audit must never break the request path
        db.rollback()
        log.exception("failed to write audit event")
    finally:
        db.close()
