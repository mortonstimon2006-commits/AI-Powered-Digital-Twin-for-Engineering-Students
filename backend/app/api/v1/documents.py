"""Resume / job-description upload and analysis. Files are stored outside any static
directory under DATA_DIR/uploads/<user_id>/<random id>.<ext> and only ever returned through
the authorised download endpoint (as an attachment, with nosniff)."""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, File, Form, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import Field
from sqlalchemy import select

from app.config import get_settings
from app.deps import DB, CurrentUser
from app.errors import AppError, NotFound
from app.models import Document, StudentSkill
from app.schemas.common import Message, StrictModel
from app.security.ratelimit import UPLOAD_USER, limiter
from app.services import audit
from app.services.career.gap_engine import analyse_all_roles
from app.services.catalogue import load_catalogue
from app.services.documents.extract import RejectedFile, extract
from app.services.documents.parse import analyse_job_description, analyse_resume
from app.services.rag.ollama_client import OllamaUnavailable
from app.services.rag.store import delete_document, index_chunks
from app.services.rag.text import chunk_text, redact_pii
from app.services.twin.history import ensure_snapshot, estimates_for

router = APIRouter(prefix="/documents", tags=["documents"])
log = logging.getLogger("twinpath.documents")
MAX_DOCS_PER_USER = 20


def _doc_out(d: Document) -> dict[str, Any]:
    return {
        "id": d.id,
        "kind": d.kind,
        "title": d.title,
        "original_filename": d.original_filename,
        "mime_type": d.mime_type,
        "size_bytes": d.size_bytes,
        "status": d.status,
        "error": d.error,
        "chunk_count": d.chunk_count,
        "injection_flags": d.injection_flags,
        "confirmed_at": d.confirmed_at,
        "retention_until": d.retention_until,
        "created_at": d.created_at,
        "extracted": d.extracted,
    }


def _owned(db: DB, user_id: uuid.UUID, doc_id: uuid.UUID) -> Document:
    d = db.scalar(select(Document).where(Document.id == doc_id, Document.owner_id == user_id))
    if d is None:
        raise NotFound("Document not found.")
    return d


def _safe_name(name: str | None) -> str | None:
    if not name:
        return None
    base = name.replace("\\", "/").split("/")[-1]
    return "".join(c for c in base if c.isalnum() or c in " ._-()")[:120] or None


def _index_private(doc: Document, text: str, user_id: uuid.UUID) -> None:
    try:
        result = index_chunks(
            doc_id=str(doc.id),
            title=doc.title,
            scope="private",
            owner_id=user_id,
            chunks=chunk_text(redact_pii(text)),
            source=doc.kind,
        )
        doc.status, doc.chunk_count, doc.injection_flags = "indexed", result.chunks, result.flagged
    except OllamaUnavailable:
        doc.status = "processed"
        doc.error = "Analysed, but not indexed for the mentor because the local embedding model is unavailable."


@router.get("")
def list_documents(principal: CurrentUser, db: DB) -> dict[str, Any]:
    rows = db.scalars(select(Document).where(Document.owner_id == principal.id).order_by(Document.created_at.desc()))
    return {"items": [_doc_out(d) for d in rows]}


@router.post("", status_code=status.HTTP_201_CREATED)
def upload_document(
    principal: CurrentUser, db: DB, file: UploadFile = File(...), kind: Literal["resume", "job_description"] = Form(...)
) -> dict[str, Any]:
    limiter.hit(UPLOAD_USER, str(principal.id))
    s = get_settings()
    data = file.file.read(s.max_upload_bytes + 1)
    if len(data) > s.max_upload_bytes:
        raise AppError(f"Files are limited to {s.max_upload_mb} MB.", code="payload_too_large", status_code=413)
    count = len(db.scalars(select(Document.id).where(Document.owner_id == principal.id)).all())
    if count >= MAX_DOCS_PER_USER:
        raise AppError("Document limit reached; delete older documents first.", code="limit_reached", status_code=422)
    try:
        ex = extract(data)
    except RejectedFile as exc:
        audit.record_standalone("document.rejected", actor_id=principal.id, outcome="denied", details={"reason": str(exc)[:120]})
        raise AppError(str(exc), code="file_rejected", status_code=422) from exc

    doc_id = uuid.uuid4()
    rel = f"{principal.id}/{doc_id.hex}.{ex.ext}"
    path = s.data_dir / "uploads" / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)

    catalogue = load_catalogue(db)
    analysis = analyse_resume(ex.text, catalogue) if kind == "resume" else analyse_job_description(ex.text, catalogue)
    analysis["warnings"] = ex.warnings
    doc = Document(
        id=doc_id,
        owner_id=principal.id,
        scope="private",
        kind=kind,
        title=(_safe_name(file.filename) or kind.replace("_", " ").title())[:160],
        original_filename=_safe_name(file.filename),
        mime_type=ex.mime,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        storage_path=rel,
        status="processed",
        extracted=analysis,
        retention_until=datetime.now(UTC) + timedelta(days=s.document_retention_days),
    )
    db.add(doc)
    db.flush()
    if ex.text.strip():
        _index_private(doc, ex.text, principal.id)
    audit.record(
        db,
        "document.uploaded",
        actor_id=principal.id,
        target_type="document",
        target_id=doc.id,
        details={"kind": kind, "size": len(data), "type": ex.ext},
    )
    db.commit()
    return _doc_out(doc)


class JobTextIn(StrictModel):
    title: str = Field(default="Job description", min_length=1, max_length=160)
    text: str = Field(min_length=30, max_length=20000)


@router.post("/job-description", status_code=status.HTTP_201_CREATED)
def paste_job_description(body: JobTextIn, principal: CurrentUser, db: DB) -> dict[str, Any]:
    limiter.hit(UPLOAD_USER, str(principal.id))
    catalogue = load_catalogue(db)
    raw = body.text.encode("utf-8")
    doc = Document(
        owner_id=principal.id,
        scope="private",
        kind="job_description",
        title=body.title,
        mime_type="text/plain",
        size_bytes=len(raw),
        sha256=hashlib.sha256(raw).hexdigest(),
        status="processed",
        extracted=analyse_job_description(body.text, catalogue),
        retention_until=datetime.now(UTC) + timedelta(days=get_settings().document_retention_days),
    )
    db.add(doc)
    db.flush()
    _index_private(doc, body.text, principal.id)
    db.commit()
    return _doc_out(doc)


@router.get("/{doc_id}")
def get_document(doc_id: uuid.UUID, principal: CurrentUser, db: DB) -> dict[str, Any]:
    return _doc_out(_owned(db, principal.id, doc_id))


@router.get("/{doc_id}/download")
def download_document(doc_id: uuid.UUID, principal: CurrentUser, db: DB) -> FileResponse:
    d = _owned(db, principal.id, doc_id)
    if not d.storage_path:
        raise NotFound("This document has no stored file.")
    base = (get_settings().data_dir / "uploads").resolve()
    path = (base / d.storage_path).resolve()
    if base not in path.parents or not path.is_file():
        raise NotFound("File not found.")
    ext = path.suffix
    return FileResponse(
        path,
        media_type=d.mime_type,
        filename=(d.original_filename or f"document{ext}"),
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"},
        content_disposition_type="attachment",
    )


@router.delete("/{doc_id}", response_model=Message)
def delete_doc(doc_id: uuid.UUID, principal: CurrentUser, db: DB) -> Message:
    d = _owned(db, principal.id, doc_id)
    try:
        delete_document(str(d.id), "private")
    except Exception:
        log.warning("vector delete failed", extra={"ctx": {"doc": str(d.id)}})
    if d.storage_path:
        base = (get_settings().data_dir / "uploads").resolve()
        path = (base / d.storage_path).resolve()
        if base in path.parents and path.exists():
            path.unlink()
    db.delete(d)
    audit.record(db, "document.deleted", actor_id=principal.id, target_type="document", target_id=doc_id)
    db.commit()
    return Message(message="Document and its derived data deleted.")


class ConfirmSkill(StrictModel):
    skill_id: int
    self_rating: int = Field(ge=0, le=4)


class ConfirmSkillsIn(StrictModel):
    skills: list[ConfirmSkill] = Field(min_length=1, max_length=60)


@router.post("/{doc_id}/confirm-skills", response_model=Message)
def confirm_skills(doc_id: uuid.UUID, body: ConfirmSkillsIn, principal: CurrentUser, db: DB) -> Message:
    d = _owned(db, principal.id, doc_id)
    if d.kind != "resume":
        raise AppError("Only resume suggestions can be confirmed.", code="invalid_document", status_code=422)
    suggested = {s["skill_id"] for s in d.extracted.get("skills", [])}
    chosen = {c.skill_id for c in body.skills}
    if not chosen <= suggested:
        raise AppError("Only skills suggested from this resume can be confirmed here.", code="invalid_skill", status_code=422)
    existing = {s.skill_id: s for s in db.scalars(select(StudentSkill).where(StudentSkill.user_id == principal.id))}
    for c in body.skills:
        if c.skill_id in existing:
            existing[c.skill_id].self_rating, existing[c.skill_id].source = c.self_rating, "resume"
        else:
            db.add(StudentSkill(user_id=principal.id, skill_id=c.skill_id, self_rating=c.self_rating, source="resume"))
    d.confirmed_at = datetime.now(UTC)
    ensure_snapshot(db, principal.id, "resume_skills_confirmed")
    db.commit()
    return Message(message=f"Added {len(body.skills)} self-reported skill rating(s) from your resume.")


class CompareIn(StrictModel):
    job_description_id: uuid.UUID
    resume_id: uuid.UUID | None = None


@router.post("/compare")
def compare(body: CompareIn, principal: CurrentUser, db: DB) -> dict[str, Any]:
    jd = _owned(db, principal.id, body.job_description_id)
    if jd.kind != "job_description":
        raise AppError("job_description_id must refer to a job description.", code="invalid_document", status_code=422)
    resume = _owned(db, principal.id, body.resume_id) if body.resume_id else None
    _, catalogue, estimates = estimates_for(db, principal.id)
    resume_skills = {s["skill_id"] for s in (resume.extracted.get("skills", []) if resume else [])}
    rows = []
    for s in jd.extracted.get("skills", []):
        e = estimates.get(s["skill_id"])
        status_ = "missing"
        if e is not None and e.known:
            status_ = "demonstrated" if e.status in ("assessed", "verified_evidence") else "claimed"
        rows.append(
            {
                "skill_id": s["skill_id"],
                "skill": s["name"],
                "jd_weight": s.get("weight", 1),
                "twin_level": e.level if e else None,
                "twin_status": e.status if e else "unknown",
                "in_resume": s["skill_id"] in resume_skills if resume else None,
                "status": status_,
            }
        )
    rows.sort(key=lambda r: (r["status"] != "missing", -r["jd_weight"], r["skill"]))
    jd_skill_ids = {s["skill_id"] for s in jd.extracted.get("skills", [])}
    role_overlap: list[dict[str, Any]] = []
    for m in analyse_all_roles(list(catalogue.roles.values()), estimates, catalogue):
        role_skills = {q.skill_id for q in catalogue.roles[m.role_id].requirements}
        union = role_skills | jd_skill_ids
        role_overlap.append(
            {
                "role_id": m.role_id,
                "role_name": m.role_name,
                "jd_overlap": round(len(role_skills & jd_skill_ids) / len(union), 3) if union else 0,
            }
        )
    role_overlap.sort(key=lambda r: -r["jd_overlap"])
    return {
        "skills": rows,
        "summary": {
            "total": len(rows),
            "missing": sum(r["status"] == "missing" for r in rows),
            "claimed_only": sum(r["status"] == "claimed" for r in rows),
            "demonstrated": sum(r["status"] == "demonstrated" for r in rows),
        },
        "closest_roles": role_overlap[:3],
        "note": (
            "Comparison uses skills recognised from the TwinPath catalogue. 'Claimed' means self-reported or "
            "unverified; 'missing' means not recorded in your twin. This is not a hiring assessment."
        ),
    }
