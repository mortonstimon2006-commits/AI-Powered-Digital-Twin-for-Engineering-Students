"""Administrator interfaces (strictly role-gated, audited)."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any, Literal

import networkx as nx
from fastapi import APIRouter, File, Form, Query, UploadFile, status
from pydantic import Field
from sqlalchemy import delete, func, select, text, update

from app.config import get_settings
from app.db import get_engine, privileged_scope, rowcount
from app.deps import DB, AdminUser
from app.errors import AppError, Conflict, NotFound
from app.ml.registry import registry
from app.models import (
    AuditEvent,
    CareerRole,
    Document,
    LearningResource,
    MentorLink,
    ModelVersion,
    ResourceSkill,
    RoleSkillRequirement,
    Skill,
    SkillPrerequisite,
    User,
    UserFeedback,
)
from app.models.catalogue import SKILL_CATEGORIES
from app.schemas.common import Message, StrictModel
from app.services import audit
from app.services.auth_service import revoke_all_sessions
from app.services.catalogue import snapshot_role_version
from app.services.documents.extract import RejectedFile, extract
from app.services.link_checker import UnsafeUrl, assert_public_https, validate_resources
from app.services.privacy import apply_retention
from app.services.rag import store
from app.services.rag.knowledge_base import reindex_global
from app.services.rag.mentor import gate
from app.services.rag.ollama_client import OllamaUnavailable, fetch_status, invalidate_status
from app.services.rag.text import chunk_text

router = APIRouter(prefix="/admin", tags=["admin"])


# ----------------------------------------------------------------------------- system


@router.get("/system")
def system_status(admin: AdminUser, db: DB) -> dict[str, Any]:
    invalidate_status()
    db_ok = True
    try:
        with get_engine().connect() as c:
            c.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    with privileged_scope(db):
        counts = {
            "users": db.scalar(select(func.count(User.id))),
            "students": db.scalar(select(func.count(User.id)).where(User.role == "student")),
            "predictions": db.scalar(text("SELECT count(*) FROM predictions")),
            "roadmaps": db.scalar(text("SELECT count(*) FROM roadmaps")),
            "documents": db.scalar(select(func.count(Document.id))),
            "readiness_labels": db.scalar(text("SELECT count(*) FROM readiness_labels")),
            "research_consented_labels": db.scalar(text("SELECT count(*) FROM readiness_labels WHERE is_research_consented")),
        }
    return {
        "database": "ok" if db_ok else "unavailable",
        "readiness_model": registry.status(),
        "ollama": fetch_status(timeout=3.0),
        "mentor_queue": gate().stats(),
        "vector_store": store.stats(),
        "counts": counts,
        "environment": get_settings().twinpath_env.value,
    }


@router.post("/retention/run")
def run_retention(admin: AdminUser, db: DB) -> dict[str, Any]:
    with privileged_scope(db):
        result = apply_retention(db)
    audit.record(db, "admin.retention_run", actor_id=admin.id, details=result)
    db.commit()
    return result


@router.get("/audit")
def audit_log(
    admin: AdminUser,
    db: DB,
    action: str | None = Query(default=None, max_length=64),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    q = select(AuditEvent)
    if action:
        q = q.where(AuditEvent.action.like(f"{action}%"))
    rows = db.scalars(q.order_by(AuditEvent.occurred_at.desc()).offset(offset).limit(limit)).all()
    return {
        "items": [
            {
                "id": e.id,
                "occurred_at": e.occurred_at,
                "actor_id": e.actor_id,
                "action": e.action,
                "outcome": e.outcome,
                "target_type": e.target_type,
                "target_id": e.target_id,
                "ip_prefix": e.ip_prefix,
                "details": e.details,
            }
            for e in rows
        ],
        "limit": limit,
        "offset": offset,
    }


@router.get("/feedback")
def feedback_list(
    admin: AdminUser,
    db: DB,
    target_type: str | None = Query(default=None, max_length=24),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    """Recent feedback, newest first. Anonymous by design: no user identity is returned, so
    administrators can read what people wrote without seeing who wrote it."""
    with privileged_scope(db):
        q = select(UserFeedback)
        if target_type:
            q = q.where(UserFeedback.target_type == target_type)
        total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
        rows = db.scalars(q.order_by(UserFeedback.created_at.desc()).limit(limit).offset(offset)).all()
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [
            {
                "id": f.id,
                "created_at": f.created_at,
                "target_type": f.target_type,
                "target_id": f.target_id,
                "rating": f.rating,
                "comment": f.comment,
            }
            for f in rows
        ],
    }


@router.get("/feedback/summary")
def feedback_summary(admin: AdminUser, db: DB) -> dict[str, Any]:
    with privileged_scope(db):
        rows = db.execute(
            select(UserFeedback.target_type, func.count(), func.avg(UserFeedback.rating)).group_by(UserFeedback.target_type)
        ).all()
    return {
        "items": [{"target_type": t, "count": n, "mean_rating": round(float(m), 2)} for t, n, m in rows],
        "note": "Self-reported usefulness ratings; not a controlled evaluation.",
    }


# ----------------------------------------------------------------------------- users


@router.get("/users")
def list_users(
    admin: AdminUser,
    db: DB,
    search: str | None = Query(default=None, max_length=80),
    role: Literal["student", "mentor", "admin"] | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    q = select(User)
    if search:
        q = q.where(User.email.like(f"%{search.lower()}%") | User.display_name.ilike(f"%{search}%"))
    if role:
        q = q.where(User.role == role)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(q.order_by(User.created_at.desc()).offset(offset).limit(limit)).all()
    return {
        "items": [
            {
                "id": u.id,
                "email": u.email,
                "display_name": u.display_name,
                "role": u.role,
                "is_active": u.is_active,
                "email_verified": u.email_verified_at is not None,
                "mfa_enabled": u.mfa_enabled_at is not None,
                "created_at": u.created_at,
                "last_login_at": u.last_login_at,
            }
            for u in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


class UserPatchIn(StrictModel):
    role: Literal["student", "mentor", "admin"] | None = None
    is_active: bool | None = None


@router.patch("/users/{user_id}")
def patch_user(user_id: uuid.UUID, body: UserPatchIn, admin: AdminUser, db: DB) -> dict[str, Any]:
    if user_id == admin.id:
        raise AppError("Administrators cannot change their own role or status.", code="self_change", status_code=422)
    u = db.get(User, user_id)
    if u is None:
        raise NotFound("User not found.")
    changes: dict[str, Any] = {}
    if body.role and body.role != u.role:
        changes["role"] = [u.role, body.role]
        u.role = body.role
    if body.is_active is not None and body.is_active != u.is_active:
        changes["is_active"] = [u.is_active, body.is_active]
        u.is_active = body.is_active
    if changes:
        revoke_all_sessions(db, u.id)  # privilege changes take effect immediately
        audit.record(db, "admin.user_updated", actor_id=admin.id, target_type="user", target_id=u.id, details=changes)
    db.commit()
    return {"id": u.id, "role": u.role, "is_active": u.is_active}


class MentorLinkIn(StrictModel):
    mentor_id: uuid.UUID
    student_id: uuid.UUID


@router.get("/mentor-links")
def list_links(admin: AdminUser, db: DB) -> dict[str, Any]:
    rows = db.execute(select(MentorLink, User.display_name).join(User, User.id == MentorLink.mentor_id)).all()
    students = {u.id: u.display_name for u in db.scalars(select(User).where(User.role == "student"))}
    return {
        "items": [
            {
                "mentor_id": link.mentor_id,
                "mentor": name,
                "student_id": link.student_id,
                "student": students.get(link.student_id),
                "created_at": link.created_at,
            }
            for link, name in rows
        ]
    }


@router.post("/mentor-links", response_model=Message, status_code=status.HTTP_201_CREATED)
def add_link(body: MentorLinkIn, admin: AdminUser, db: DB) -> Message:
    mentor, student = db.get(User, body.mentor_id), db.get(User, body.student_id)
    if mentor is None or mentor.role not in ("mentor", "admin") or student is None or student.role != "student":
        raise AppError("Choose an existing mentor and student.", code="invalid_link", status_code=422)
    if db.get(MentorLink, (body.mentor_id, body.student_id)):
        raise Conflict("This mentor is already assigned to the student.")
    db.add(MentorLink(mentor_id=body.mentor_id, student_id=body.student_id, created_by=admin.id))
    audit.record(db, "admin.mentor_link_added", actor_id=admin.id, target_type="user", target_id=body.student_id)
    db.commit()
    return Message(message="Mentor assigned. They gain access only while the student grants mentor sharing.")


@router.delete("/mentor-links/{mentor_id}/{student_id}", response_model=Message)
def remove_link(mentor_id: uuid.UUID, student_id: uuid.UUID, admin: AdminUser, db: DB) -> Message:
    n = rowcount(db.execute(delete(MentorLink).where(MentorLink.mentor_id == mentor_id, MentorLink.student_id == student_id)))
    if not n:
        raise NotFound("Link not found.")
    audit.record(db, "admin.mentor_link_removed", actor_id=admin.id, target_type="user", target_id=student_id)
    db.commit()
    return Message(message="Mentor assignment removed.")


# ----------------------------------------------------------------------------- catalogue


class RequirementIn(StrictModel):
    skill_id: int
    required_level: int = Field(ge=1, le=4)
    importance: float = Field(gt=0, le=1)
    is_core: bool = True
    evidence_expected: Literal["any", "project", "assessment"] = "any"
    alt_group: str | None = Field(default=None, max_length=32, pattern=r"^[a-z0-9-]+$")
    rationale: str = Field(default="", max_length=500)


class RoleIn(StrictModel):
    slug: str = Field(min_length=3, max_length=64, pattern=r"^[a-z0-9-]+$")
    name: str = Field(min_length=3, max_length=80)
    summary: str = Field(min_length=10, max_length=300)
    description: str = Field(default="", max_length=4000)
    source_note: str = Field(min_length=10, max_length=2000)
    requirements: list[RequirementIn] = Field(min_length=1, max_length=40)


def _apply_requirements(db: DB, role: CareerRole, reqs: list[RequirementIn]) -> None:
    ids = [r.skill_id for r in reqs]
    if len(set(ids)) != len(ids):
        raise AppError("Each skill may appear once per role.", code="duplicate_skill", status_code=422)
    known = set(db.scalars(select(Skill.id).where(Skill.id.in_(ids))))
    if known != set(ids):
        raise AppError("Unknown skill id in requirements.", code="invalid_skill", status_code=422)
    role.requirements = [RoleSkillRequirement(**r.model_dump()) for r in reqs]


@router.post("/roles", status_code=status.HTTP_201_CREATED)
def create_role(body: RoleIn, admin: AdminUser, db: DB) -> dict[str, Any]:
    if db.scalar(select(CareerRole.id).where(CareerRole.slug == body.slug)):
        raise Conflict("A role with this slug already exists.")
    role = CareerRole(**body.model_dump(exclude={"requirements"}), version=1, updated_by=admin.id)
    _apply_requirements(db, role, body.requirements)
    db.add(role)
    db.flush()
    snapshot_role_version(db, role, admin.id)
    audit.record(db, "admin.role_created", actor_id=admin.id, target_type="role", target_id=role.id)
    db.commit()
    return {"id": role.id, "version": role.version}


@router.put("/roles/{role_id}")
def update_role(role_id: int, body: RoleIn, admin: AdminUser, db: DB) -> dict[str, Any]:
    role = db.get(CareerRole, role_id)
    if role is None:
        raise NotFound("Role not found.")
    for k, v in body.model_dump(exclude={"requirements"}).items():
        setattr(role, k, v)
    _apply_requirements(db, role, body.requirements)
    role.version += 1
    role.updated_by = admin.id
    db.flush()
    snapshot_role_version(db, role, admin.id)
    audit.record(
        db, "admin.role_updated", actor_id=admin.id, target_type="role", target_id=role.id, details={"version": role.version}
    )
    db.commit()
    return {"id": role.id, "version": role.version}


@router.delete("/roles/{role_id}", response_model=Message)
def deactivate_role(role_id: int, admin: AdminUser, db: DB) -> Message:
    role = db.get(CareerRole, role_id)
    if role is None:
        raise NotFound("Role not found.")
    role.is_active = False
    audit.record(db, "admin.role_deactivated", actor_id=admin.id, target_type="role", target_id=role.id)
    db.commit()
    return Message(message="Role deactivated (kept for history).")


class SkillIn(StrictModel):
    slug: str = Field(min_length=2, max_length=64, pattern=r"^[a-z0-9-]+$")
    name: str = Field(min_length=2, max_length=80)
    category: str
    kind: Literal["concept", "technology", "practice"] = "concept"
    description: str = Field(default="", max_length=2000)
    aliases: list[str] = Field(default_factory=list, max_length=20)
    practice_exercise: str = Field(default="", max_length=2000)
    completion_criteria: str = Field(default="", max_length=1000)


@router.post("/skills", status_code=status.HTTP_201_CREATED)
def create_skill(body: SkillIn, admin: AdminUser, db: DB) -> dict[str, Any]:
    if body.category not in SKILL_CATEGORIES:
        raise AppError(f"category must be one of {SKILL_CATEGORIES}", code="invalid_category", status_code=422)
    if db.scalar(select(Skill.id).where(Skill.slug == body.slug)):
        raise Conflict("A skill with this slug already exists.")
    sk = Skill(**{**body.model_dump(), "aliases": [a.strip().lower() for a in body.aliases if a.strip()]})
    db.add(sk)
    audit.record(db, "admin.skill_created", actor_id=admin.id, target_type="skill", target_id=body.slug)
    db.commit()
    return {"id": sk.id}


class PrerequisitesIn(StrictModel):
    prerequisites: list[tuple[int, int]] = Field(
        default_factory=list, max_length=10, description="[(prerequisite_skill_id, min_level)]"
    )


@router.put("/skills/{skill_id}/prerequisites")
def set_prerequisites(skill_id: int, body: PrerequisitesIn, admin: AdminUser, db: DB) -> dict[str, Any]:
    if db.get(Skill, skill_id) is None:
        raise NotFound("Skill not found.")
    g = nx.DiGraph()
    for p in db.scalars(select(SkillPrerequisite).where(SkillPrerequisite.skill_id != skill_id)):
        g.add_edge(p.prerequisite_id, p.skill_id)
    for pid, lvl in body.prerequisites:
        if not 1 <= lvl <= 4 or pid == skill_id or db.get(Skill, pid) is None:
            raise AppError("Invalid prerequisite.", code="invalid_prerequisite", status_code=422)
        g.add_edge(pid, skill_id)
    if not nx.is_directed_acyclic_graph(g):
        raise AppError("This change would create a prerequisite cycle.", code="prerequisite_cycle", status_code=422)
    db.execute(delete(SkillPrerequisite).where(SkillPrerequisite.skill_id == skill_id))
    for pid, lvl in body.prerequisites:
        db.add(SkillPrerequisite(skill_id=skill_id, prerequisite_id=pid, min_level=lvl))
    db.execute(update(Skill).where(Skill.id == skill_id).values(updated_at=func.now()))
    audit.record(db, "admin.prerequisites_set", actor_id=admin.id, target_type="skill", target_id=skill_id)
    db.commit()
    return {"skill_id": skill_id, "prerequisites": body.prerequisites}


class ResourceIn(StrictModel):
    title: str = Field(min_length=3, max_length=160)
    provider: str = Field(min_length=2, max_length=80)
    url: str = Field(max_length=500, pattern=r"^https://")
    resource_type: Literal["documentation", "course", "book", "tutorial", "practice", "video"]
    cost: Literal["free", "freemium", "paid"] = "free"
    level_min: int = Field(ge=1, le=4)
    level_max: int = Field(ge=1, le=4)
    est_hours_min: int = Field(ge=1, le=500)
    est_hours_max: int = Field(ge=1, le=1000)
    description: str = Field(default="", max_length=1000)
    skill_ids: list[int] = Field(min_length=1, max_length=10)


@router.get("/resources")
def list_resources(admin: AdminUser, db: DB) -> dict[str, Any]:
    rows = db.scalars(select(LearningResource).order_by(LearningResource.title)).all()
    links: dict[int, list[int]] = {}
    for rs in db.scalars(select(ResourceSkill)):
        links.setdefault(rs.resource_id, []).append(rs.skill_id)
    return {
        "items": [
            {
                "id": r.id,
                "title": r.title,
                "provider": r.provider,
                "url": r.url,
                "type": r.resource_type,
                "cost": r.cost,
                "verification_status": r.verification_status,
                "last_checked_at": r.last_checked_at,
                "last_http_status": r.last_http_status,
                "is_active": r.is_active,
                "skill_ids": links.get(r.id, []),
            }
            for r in rows
        ]
    }


@router.post("/resources", status_code=status.HTTP_201_CREATED)
def create_resource(body: ResourceIn, admin: AdminUser, db: DB) -> dict[str, Any]:
    if body.level_max < body.level_min or body.est_hours_max < body.est_hours_min:
        raise AppError("Ranges must be ordered (min ≤ max).", code="invalid_range", status_code=422)
    try:
        assert_public_https(body.url)
    except UnsafeUrl as exc:
        raise AppError(f"URL rejected: {exc}", code="unsafe_url", status_code=422) from exc
    res = LearningResource(**body.model_dump(exclude={"skill_ids"}), verification_status="unverified")
    db.add(res)
    db.flush()
    for sid in set(body.skill_ids):
        if db.get(Skill, sid) is None:
            raise AppError("Unknown skill id.", code="invalid_skill", status_code=422)
        db.add(ResourceSkill(resource_id=res.id, skill_id=sid))
    audit.record(db, "admin.resource_created", actor_id=admin.id, target_type="resource", target_id=res.id)
    db.commit()
    return {"id": res.id, "verification_status": res.verification_status}


@router.delete("/resources/{resource_id}", response_model=Message)
def deactivate_resource(resource_id: int, admin: AdminUser, db: DB) -> Message:
    res = db.get(LearningResource, resource_id)
    if res is None:
        raise NotFound("Resource not found.")
    res.is_active = False
    audit.record(db, "admin.resource_deactivated", actor_id=admin.id, target_type="resource", target_id=resource_id)
    db.commit()
    return Message(message="Resource deactivated.")


class ValidateIn(StrictModel):
    resource_ids: list[int] | None = Field(default=None, max_length=200)


@router.post("/resources/validate")
def validate_links(body: ValidateIn, admin: AdminUser, db: DB) -> dict[str, Any]:
    report = validate_resources(db, body.resource_ids)
    audit.record(db, "admin.resources_validated", actor_id=admin.id, details={"checked": len(report)})
    db.commit()
    return {"items": report}


# ----------------------------------------------------------------------------- models


@router.get("/models")
def list_models(admin: AdminUser, db: DB) -> dict[str, Any]:
    rows = db.scalars(select(ModelVersion).order_by(ModelVersion.created_at.desc())).all()
    return {
        "active": registry.status(),
        "items": [
            {
                "id": m.id,
                "version": m.version,
                "algorithm": m.algorithm,
                "status": m.status,
                "is_synthetic": m.is_synthetic,
                "metrics": m.metrics,
                "trained_at": m.trained_at,
                "activated_at": m.activated_at,
                "notes": m.notes,
            }
            for m in rows
        ],
    }


@router.post("/models/{model_id}/activate")
def activate_model(model_id: int, admin: AdminUser, db: DB) -> dict[str, Any]:
    mv = db.get(ModelVersion, model_id)
    if mv is None:
        raise NotFound("Model not found.")
    try:  # verify the artifact loads and passes integrity checks BEFORE switching
        registry.load_artifact(mv.artifact_path, mv.artifact_sha256, mv.id, mv.version)
    except Exception as exc:
        raise AppError(
            f"Model failed verification and was not activated: {str(exc)[:200]}", code="model_invalid", status_code=422
        ) from exc
    db.execute(update(ModelVersion).where(ModelVersion.kind == mv.kind, ModelVersion.status == "active").values(status="retired"))
    db.flush()
    mv.status, mv.activated_at = "active", datetime.now(UTC)
    audit.record(db, "admin.model_activated", actor_id=admin.id, target_type="model", target_id=mv.version)
    db.commit()
    registry.warm()
    return {"active": registry.status()}


@router.post("/models/{model_id}/retire")
def retire_model(model_id: int, admin: AdminUser, db: DB) -> dict[str, Any]:
    mv = db.get(ModelVersion, model_id)
    if mv is None:
        raise NotFound("Model not found.")
    mv.status = "retired"
    audit.record(db, "admin.model_retired", actor_id=admin.id, target_type="model", target_id=mv.version)
    db.commit()
    registry.warm()
    return {"active": registry.status()}


# ----------------------------------------------------------------------------- knowledge base


@router.get("/knowledge")
def list_knowledge(admin: AdminUser, db: DB) -> dict[str, Any]:
    rows = db.scalars(select(Document).where(Document.scope == "global").order_by(Document.title)).all()
    return {
        "stats": store.stats(),
        "items": [
            {
                "id": d.id,
                "title": d.title,
                "source": d.original_filename,
                "status": d.status,
                "chunks": d.chunk_count,
                "injection_flags": d.injection_flags,
                "error": d.error,
                "created_at": d.created_at,
            }
            for d in rows
        ],
    }


@router.post("/knowledge/reindex")
def reindex(admin: AdminUser, db: DB) -> dict[str, Any]:
    try:
        with privileged_scope(db):
            result = reindex_global(db)
    except OllamaUnavailable as exc:
        raise AppError(
            "The local embedding model is unavailable; the knowledge base was not re-indexed.",
            code="embeddings_unavailable",
            status_code=503,
        ) from exc
    audit.record(db, "admin.kb_reindexed", actor_id=admin.id, details={"chunks": result["chunks"]})
    db.commit()
    return result


@router.post("/knowledge/upload", status_code=status.HTTP_201_CREATED)
def upload_knowledge(
    admin: AdminUser, db: DB, file: UploadFile = File(...), title: str = Form(..., min_length=3, max_length=160)
) -> dict[str, Any]:
    s = get_settings()
    data = file.file.read(s.max_upload_bytes + 1)
    if len(data) > s.max_upload_bytes:
        raise AppError(f"Files are limited to {s.max_upload_mb} MB.", code="payload_too_large", status_code=413)
    try:
        ex = extract(data)
    except RejectedFile as exc:
        raise AppError(str(exc), code="file_rejected", status_code=422) from exc
    doc = Document(
        owner_id=None,
        scope="global",
        kind="knowledge",
        title=title,
        original_filename=f"upload:{uuid.uuid4().hex[:8]}",
        mime_type=ex.mime,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        status="processed",
    )
    with privileged_scope(db):
        db.add(doc)
        db.flush()
        try:
            result = store.index_chunks(
                doc_id=str(doc.id), title=title, scope="global", owner_id=None, chunks=chunk_text(ex.text), source="admin upload"
            )
            doc.status, doc.chunk_count, doc.injection_flags = "indexed", result.chunks, result.flagged
        except OllamaUnavailable:
            doc.status, doc.error = "failed", "Embedding model unavailable"
        audit.record(db, "admin.kb_uploaded", actor_id=admin.id, target_type="document", target_id=doc.id)
        db.commit()
    return {"id": doc.id, "status": doc.status, "chunks": doc.chunk_count, "injection_flags": doc.injection_flags}


@router.delete("/knowledge/{doc_id}", response_model=Message)
def delete_knowledge(doc_id: uuid.UUID, admin: AdminUser, db: DB) -> Message:
    with privileged_scope(db):
        doc = db.scalar(select(Document).where(Document.id == doc_id, Document.scope == "global"))
        if doc is None:
            raise NotFound("Document not found.")
        store.delete_document(str(doc.id), "global")
        db.delete(doc)
        audit.record(db, "admin.kb_deleted", actor_id=admin.id, target_type="document", target_id=doc_id)
        db.commit()
    return Message(message="Knowledge document removed.")
