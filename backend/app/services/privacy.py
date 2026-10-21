"""Consent management, data export, account deletion and retention enforcement."""

from __future__ import annotations

import logging
import shutil
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.inspection import inspect as sa_inspect
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import rowcount
from app.models import (
    AssessmentResult,
    AuditEvent,
    AuthToken,
    Certification,
    Consent,
    Document,
    Experience,
    MentorConversation,
    MentorMessage,
    Prediction,
    Project,
    ReadinessLabel,
    Roadmap,
    RoadmapEvent,
    RoadmapItem,
    SkillEvidence,
    StudentProfile,
    StudentRolePreference,
    StudentSkill,
    TwinSnapshot,
    User,
    UserFeedback,
    UserSession,
    WhatIfScenario,
)
from app.services.auth_service import POLICY_VERSION

log = logging.getLogger("twinpath.privacy")

CONSENT_INFO = {
    "profile_processing": ("Process the profile data you enter to provide the app's features.", True),
    "mentor_sharing": ("Let your assigned mentor view your digital twin and record assessments.", False),
    "research_use": (
        "Allow assessor labels and the profile snapshots they refer to to be used to train and evaluate future readiness models.",
        False,
    ),
    "attendance_data": ("Store your attendance percentage as part of your academic profile.", False),
}


def consents(db: Session, user_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = {c.purpose: c for c in db.scalars(select(Consent).where(Consent.user_id == user_id))}
    return [
        {
            "purpose": p,
            "description": d,
            "required": req,
            "granted": bool(rows.get(p) and rows[p].granted),
            "updated_at": rows[p].updated_at if p in rows else None,
            "policy_version": POLICY_VERSION,
        }
        for p, (d, req) in CONSENT_INFO.items()
    ]


def set_consent(db: Session, user_id: uuid.UUID, purpose: str, granted: bool) -> None:
    row = db.get(Consent, (user_id, purpose))
    if row is None:
        db.add(Consent(user_id=user_id, purpose=purpose, granted=granted, policy_version=POLICY_VERSION))
    else:
        row.granted, row.policy_version = granted, POLICY_VERSION
    if purpose == "attendance_data" and not granted:
        profile = db.get(StudentProfile, user_id)
        if profile is not None:
            profile.attendance_pct = None  # purpose limitation: data goes when consent goes


def _rows(db: Session, model: Any, column: Any, value: Any) -> list[dict[str, Any]]:
    out = []
    for obj in db.scalars(select(model).where(column == value)):
        rec = {}
        for attr in sa_inspect(model).mapper.column_attrs:
            if attr.key in ("password_hash", "mfa_secret_encrypted", "token_hash", "csrf_hash", "storage_path"):
                continue
            v = getattr(obj, attr.key)
            rec[attr.key] = v.hex() if isinstance(v, bytes) else v
        out.append(rec)
    return out


def export_user_data(db: Session, user: User) -> dict[str, Any]:
    uid = user.id
    data: dict[str, Any] = {
        "export_format": "twinpath-export-v1",
        "exported_at": datetime.now(UTC).isoformat(),
        "account": {
            "id": str(uid),
            "email": user.email,
            "display_name": user.display_name,
            "role": user.role,
            "created_at": user.created_at,
            "email_verified_at": user.email_verified_at,
            "mfa_enabled": user.mfa_enabled_at is not None,
            "last_login_at": user.last_login_at,
        },
    }
    for key, model in (
        ("consents", Consent),
        ("profile", StudentProfile),
        ("role_preferences", StudentRolePreference),
        ("skill_ratings", StudentSkill),
        ("projects", Project),
        ("experiences", Experience),
        ("certifications", Certification),
        ("assessment_results", AssessmentResult),
        ("skill_evidence", SkillEvidence),
        ("twin_snapshots", TwinSnapshot),
        ("readiness_labels", ReadinessLabel),
        ("predictions", Prediction),
        ("what_if_scenarios", WhatIfScenario),
        ("roadmaps", Roadmap),
        ("roadmap_items", RoadmapItem),
        ("roadmap_events", RoadmapEvent),
        ("mentor_conversations", MentorConversation),
        ("mentor_messages", MentorMessage),
        ("feedback", UserFeedback),
    ):
        data[key] = _rows(db, model, model.user_id, uid)
    data["documents"] = _rows(db, Document, Document.owner_id, uid)
    data["sessions"] = _rows(db, UserSession, UserSession.user_id, uid)
    data["security_events"] = [
        {"occurred_at": e.occurred_at, "action": e.action, "outcome": e.outcome}
        for e in db.scalars(select(AuditEvent).where(AuditEvent.actor_id == uid).order_by(AuditEvent.occurred_at))
    ]
    return data


def _remove_user_files(user_id: uuid.UUID) -> None:
    base = (get_settings().data_dir / "uploads").resolve()
    target = (base / str(user_id)).resolve()
    if target.parent == base and target.exists():
        shutil.rmtree(target, ignore_errors=True)


def delete_account(db: Session, user: User) -> None:
    """Hard delete. Files and vectors first (so a later failure leaves no orphaned personal
    files), then the user row; ON DELETE CASCADE removes all owned rows."""
    from app.services.rag.store import delete_owner

    uid = user.id
    try:
        delete_owner(uid)
    except Exception:
        log.exception("vector cleanup failed during account deletion")
        raise
    _remove_user_files(uid)
    db.delete(user)
    db.flush()


def apply_retention(db: Session) -> dict[str, int]:
    """Run as a privileged system job (CLI / admin)."""
    from app.services.rag.store import delete_document

    s = get_settings()
    now = datetime.now(UTC)
    removed_docs = 0
    for doc in db.scalars(
        select(Document).where(Document.scope == "private", Document.retention_until.is_not(None), Document.retention_until < now)
    ):
        try:
            delete_document(str(doc.id), "private")
        except Exception:
            log.warning("vector delete failed for expired document", extra={"ctx": {"doc": str(doc.id)}})
        if doc.storage_path:
            path = (s.data_dir / "uploads" / doc.storage_path).resolve()
            if (s.data_dir / "uploads").resolve() in path.parents and path.exists():
                path.unlink()
        db.delete(doc)
        removed_docs += 1
    chat_cutoff = now - timedelta(days=s.chat_retention_days)
    msgs = rowcount(db.execute(delete(MentorMessage).where(MentorMessage.created_at < chat_cutoff)))
    convs = rowcount(db.execute(delete(MentorConversation).where(MentorConversation.updated_at < chat_cutoff)))
    sessions = rowcount(db.execute(delete(UserSession).where(UserSession.expires_at < now - timedelta(days=30))))
    tokens = rowcount(db.execute(delete(AuthToken).where(AuthToken.expires_at < now - timedelta(days=7))))
    db.flush()
    return {
        "documents": removed_docs,
        "mentor_messages": msgs or 0,
        "conversations": convs or 0,
        "sessions": sessions or 0,
        "auth_tokens": tokens or 0,
    }
