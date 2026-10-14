from __future__ import annotations

import contextlib
import json
from typing import Any, Literal

from fastapi import APIRouter, Response
from pydantic import Field
from sqlalchemy import select

from app.config import get_settings
from app.deps import DB, CurrentUser
from app.errors import AppError
from app.models import UserFeedback
from app.schemas.common import Message, StrictModel
from app.security.passwords import verify_password
from app.services import audit, privacy
from app.services.rag.ollama_client import OllamaUnavailable
from app.services.twin.history import ensure_snapshot

router = APIRouter(tags=["privacy"])


@router.get("/privacy/consents")
def get_consents(principal: CurrentUser, db: DB) -> dict[str, Any]:
    return {"items": privacy.consents(db, principal.id)}


class ConsentIn(StrictModel):
    granted: bool


@router.put("/privacy/consents/{purpose}")
def put_consent(
    purpose: Literal["mentor_sharing", "research_use", "attendance_data"], body: ConsentIn, principal: CurrentUser, db: DB
) -> dict[str, Any]:
    privacy.set_consent(db, principal.id, purpose, body.granted)
    audit.record(
        db, "privacy.consent", actor_id=principal.id, target_type="consent", target_id=purpose, details={"granted": body.granted}
    )
    if purpose == "attendance_data" and not body.granted:
        ensure_snapshot(db, principal.id, "attendance_consent_withdrawn")
    db.commit()
    return {"items": privacy.consents(db, principal.id)}


@router.get("/privacy/policy")
def policy() -> dict[str, Any]:
    s = get_settings()
    return {
        "retention_days": {
            "documents": s.document_retention_days,
            "mentor_conversations": s.chat_retention_days,
            "expired_sessions": 30,
        },
        "local_ai": {
            "runtime": "Ollama (local)",
            "chat_model": s.ollama_chat_model,
            "embed_model": s.ollama_embed_model,
            "external_ai_apis": "none",
        },
        "network_connections": [
            "PostgreSQL database (private network)",
            "Local Ollama runtime (loopback / private network only)",
            "SMTP server for account emails (only if configured)",
            "Learning-resource link checks to public https URLs (administrator-triggered only)",
        ],
        "not_collected": ["gender", "religion", "caste", "date of birth", "government identifiers"],
    }


@router.get("/privacy/export")
def export(principal: CurrentUser, db: DB) -> Response:
    data = privacy.export_user_data(db, principal.user)
    audit.record(db, "privacy.export", actor_id=principal.id)
    db.commit()
    body = json.dumps(data, default=str, indent=2).encode()
    return Response(
        content=body,
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="twinpath-export.json"', "Cache-Control": "no-store"},
    )


class DeleteAccountIn(StrictModel):
    password: str = Field(min_length=1, max_length=256)
    confirmation: Literal["DELETE MY ACCOUNT"]


@router.post("/privacy/delete-account", response_model=Message)
def delete_account(body: DeleteAccountIn, principal: CurrentUser, db: DB, response: Response) -> Message:
    if not verify_password(principal.user.password_hash, body.password):
        audit.record_standalone("privacy.delete_account", actor_id=principal.id, outcome="failure")
        raise AppError("The password is incorrect.", code="invalid_password", status_code=400)
    from app.security.tokens import keyed_digest

    ref = keyed_digest(str(principal.id), "deleted-user")
    # Vectors are keyed by owner and removed without needing the embedding model.
    with contextlib.suppress(OllamaUnavailable):
        privacy.delete_account(db, principal.user)
    # No network identifiers are retained for a deleted subject; only a keyed pseudonymous reference.
    audit.record(db, "privacy.account_deleted", actor_id=None, details={"deleted_user_ref": ref})
    db.commit()
    s = get_settings()
    response.delete_cookie(s.session_cookie_name, path="/", secure=s.cookie_secure, httponly=True, samesite="lax")
    response.delete_cookie(s.csrf_cookie_name, path="/", secure=s.cookie_secure, samesite="strict")
    return Message(message="Your account and all associated data have been permanently deleted.")


class FeedbackIn(StrictModel):
    target_type: Literal[
        "roadmap_item", "role_recommendation", "mentor_message", "prediction", "resource", "gap_analysis", "simulation", "general"
    ]
    target_id: str | None = Field(default=None, max_length=64)
    rating: int = Field(ge=1, le=5)
    comment: str = Field(default="", max_length=1000)


@router.post("/feedback", response_model=Message)
def feedback(body: FeedbackIn, principal: CurrentUser, db: DB) -> Message:
    db.add(UserFeedback(user_id=principal.id, **body.model_dump()))
    db.commit()
    return Message(message="Thank you — your feedback helps evaluate TwinPath.")


@router.get("/feedback")
def my_feedback(principal: CurrentUser, db: DB) -> dict[str, Any]:
    rows = db.scalars(
        select(UserFeedback).where(UserFeedback.user_id == principal.id).order_by(UserFeedback.created_at.desc()).limit(200)
    )
    return {
        "items": [
            {
                "id": f.id,
                "target_type": f.target_type,
                "target_id": f.target_id,
                "rating": f.rating,
                "comment": f.comment,
                "created_at": f.created_at,
            }
            for f in rows
        ]
    }
