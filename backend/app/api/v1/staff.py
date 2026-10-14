"""Mentor/assessor tools. A mentor may act on a student only when (a) an administrator has
linked them AND (b) the student currently grants the `mentor_sharing` consent. Admins may act
on any student. Every action is audited. Reads/writes are RLS-scoped to that one student."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any, Literal

from fastapi import APIRouter, Query
from pydantic import Field, field_validator
from sqlalchemy import or_, select

from app.db import privileged_scope, set_rls_subject
from app.deps import DB, StaffUser
from app.errors import AppError, NotFound
from app.models import (
    Assessment,
    AssessmentResult,
    Certification,
    Consent,
    Experience,
    MentorLink,
    Prediction,
    Project,
    ReadinessLabel,
    User,
)
from app.schemas.common import Message, StrictModel
from app.services import audit
from app.services.career.gap_engine import analyse_role
from app.services.twin.history import completeness, ensure_snapshot, estimates_for

router = APIRouter(prefix="/staff", tags=["mentor-tools"])

EVIDENCE_MODELS: tuple[tuple[Any, str, str], ...] = (
    (Project, "project", "title"),
    (Experience, "experience", "title"),
    (Certification, "certification", "name"),
)


def _accessible_student(db: DB, staff: StaffUser, student_id: uuid.UUID) -> User:
    student = db.get(User, student_id)
    if student is None or student.role != "student" or not student.is_active:
        raise NotFound("Student not found.")
    if staff.role != "admin":
        link = db.get(MentorLink, (staff.id, student_id))
        with privileged_scope(db):  # authorisation lookup only: the consent row belongs to the student
            consent = db.get(Consent, (student_id, "mentor_sharing"))
        if link is None or consent is None or not consent.granted:
            audit.record_standalone("staff.access", actor_id=staff.id, outcome="denied", target_type="user", target_id=student_id)
            raise NotFound("Student not found.")  # do not reveal whether the student exists
    set_rls_subject(db, student_id)  # RLS now scopes every query to this one student
    return student


@router.get("/students")
def list_students(
    staff: StaffUser,
    db: DB,
    search: str | None = Query(default=None, max_length=80),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    q = select(User).where(User.role == "student", User.is_active.is_(True))
    if staff.role != "admin":
        q = (
            q.join(MentorLink, (MentorLink.student_id == User.id) & (MentorLink.mentor_id == staff.id))
            .join(Consent, (Consent.user_id == User.id) & (Consent.purpose == "mentor_sharing"))
            .where(Consent.granted.is_(True))
        )
    if search:
        like = f"%{search.lower()}%"
        q = q.where(or_(User.email.like(like), User.display_name.ilike(like)))
    with privileged_scope(db):  # the consent join reads other users' consent rows
        rows = db.scalars(q.order_by(User.display_name).offset(offset).limit(limit)).all()
    return {
        "items": [{"id": u.id, "display_name": u.display_name, "email": u.email} for u in rows],
        "limit": limit,
        "offset": offset,
    }


@router.get("/students/{student_id}/overview")
def student_overview(student_id: uuid.UUID, staff: StaffUser, db: DB) -> dict[str, Any]:
    student = _accessible_student(db, staff, student_id)
    state, catalogue, estimates = estimates_for(db, student_id)
    target = state.profile.get("target_role_id")
    gaps = None
    if target in catalogue.roles:
        m = analyse_role(catalogue.roles[target], estimates, catalogue)
        gaps = {
            "role": m.role_name,
            "match": m.match,
            "match_upper": m.match_upper,
            "top": [
                {
                    "skill": g.skill_name,
                    "action": g.action,
                    "required": g.required_level,
                    "estimate": g.estimated_level,
                    "status": g.status,
                }
                for g in m.gaps
                if g.action != "maintain"
            ][:8],
        }
    pred = db.scalar(select(Prediction).where(Prediction.user_id == student_id).order_by(Prediction.created_at.desc()).limit(1))
    pending = []
    for model, kind, label in EVIDENCE_MODELS:
        for item in db.scalars(select(model).where(model.user_id == student_id, model.verification_status == "pending")):
            pending.append({"item_type": kind, "item_id": item.id, "title": getattr(item, label)})
    audit.record(db, "staff.view_student", actor_id=staff.id, target_type="user", target_id=student_id)
    db.commit()
    return {
        "student": {"id": student.id, "display_name": student.display_name},
        "profile": state.profile,
        "completeness": completeness(state, estimates),
        "skills": [
            {"skill": catalogue.skills[e.skill_id].name, "level": e.level, "status": e.status}
            for e in estimates.values()
            if e.known
        ],
        "gaps": gaps,
        "latest_readiness": {"band": pred.band, "probability": pred.probability, "created_at": pred.created_at} if pred else None,
        "pending_verifications": pending,
        "projects": [
            {"id": p.id, "title": p.title, "repo_url": p.repo_url, "verification_status": p.verification_status}
            for p in state_projects(db, student_id)
        ],
    }


def state_projects(db: DB, student_id: uuid.UUID) -> list[Project]:
    return list(db.scalars(select(Project).where(Project.user_id == student_id).order_by(Project.created_at.desc())))


class RecordAssessmentIn(StrictModel):
    assessment_id: int
    score: float = Field(ge=0)
    taken_on: date
    notes: str = Field(default="", max_length=1000)

    @field_validator("taken_on")
    @classmethod
    def _past(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("taken_on cannot be in the future")
        return v


@router.post("/students/{student_id}/assessments", response_model=Message)
def record_assessment(student_id: uuid.UUID, body: RecordAssessmentIn, staff: StaffUser, db: DB) -> Message:
    _accessible_student(db, staff, student_id)
    a = db.get(Assessment, body.assessment_id)
    if a is None or not a.is_active:
        raise AppError("Unknown assessment.", code="invalid_assessment", status_code=422)
    if body.score > float(a.max_score):
        raise AppError(f"Score cannot exceed {float(a.max_score):g}.", code="invalid_score", status_code=422)
    db.add(
        AssessmentResult(
            user_id=student_id,
            assessment_id=a.id,
            score=body.score,
            max_score=a.max_score,
            taken_on=body.taken_on,
            source="mentor_recorded",
            verification_status="verified",
            recorded_by=staff.id,
            notes=body.notes,
        )
    )
    db.flush()
    ensure_snapshot(db, student_id, "assessment_recorded")
    audit.record(
        db,
        "staff.assessment_recorded",
        actor_id=staff.id,
        target_type="user",
        target_id=student_id,
        details={"assessment": a.slug},
    )
    db.commit()
    return Message(message="Verified assessment recorded.")


class VerifyIn(StrictModel):
    item_type: Literal["project", "experience", "certification", "assessment"]
    item_id: uuid.UUID
    decision: Literal["verified", "rejected"]


@router.post("/students/{student_id}/verify", response_model=Message)
def verify_item(student_id: uuid.UUID, body: VerifyIn, staff: StaffUser, db: DB) -> Message:
    _accessible_student(db, staff, student_id)
    model: Any = {"project": Project, "experience": Experience, "certification": Certification, "assessment": AssessmentResult}[
        body.item_type
    ]
    item = db.scalar(select(model).where(model.id == body.item_id, model.user_id == student_id))
    if item is None:
        raise NotFound("Item not found.")
    item.verification_status = body.decision
    if hasattr(item, "verified_by"):
        item.verified_by, item.verified_at = staff.id, datetime.now(UTC)
    ensure_snapshot(db, student_id, f"{body.item_type}_{body.decision}")
    audit.record(
        db,
        "staff.verification",
        actor_id=staff.id,
        target_type=body.item_type,
        target_id=body.item_id,
        details={"decision": body.decision, "student": str(student_id)},
    )
    db.commit()
    return Message(message=f"Item marked {body.decision}.")


class LabelIn(StrictModel):
    label: Literal["ready", "not_ready"]
    role_id: int | None = None
    rubric: dict[str, int] = Field(default_factory=dict, max_length=10)
    notes: str = Field(default="", max_length=1000)

    @field_validator("rubric")
    @classmethod
    def _rubric(cls, v: dict[str, int]) -> dict[str, int]:
        for k, score in v.items():
            if len(k) > 40 or not 1 <= score <= 5:
                raise ValueError("rubric keys ≤40 chars, scores 1–5")
        return v


@router.post("/students/{student_id}/readiness-labels", response_model=Message)
def record_label(student_id: uuid.UUID, body: LabelIn, staff: StaffUser, db: DB) -> Message:
    """Captures the supervised target for future model training, frozen against the current
    snapshot so the label can never be paired with later (future) information."""
    _accessible_student(db, staff, student_id)
    snap = ensure_snapshot(db, student_id, "readiness_label_recorded")
    with privileged_scope(db):
        research = db.get(Consent, (student_id, "research_use"))
    db.add(
        ReadinessLabel(
            user_id=student_id,
            assessor_id=staff.id,
            snapshot_id=snap.id,
            role_id=body.role_id,
            label=body.label,
            rubric=body.rubric,
            notes=body.notes,
            is_research_consented=bool(research and research.granted),
        )
    )
    audit.record(db, "staff.readiness_label", actor_id=staff.id, target_type="user", target_id=student_id)
    db.commit()
    return Message(message="Assessor readiness label recorded.")


@router.get("/verification-queue")
def verification_queue(staff: StaffUser, db: DB) -> dict[str, Any]:
    students = list_students(staff, db, None, 200, 0)["items"]
    out = []
    for s in students:
        set_rls_subject(db, s["id"])
        for model, kind, label in EVIDENCE_MODELS:
            for item in db.scalars(select(model).where(model.user_id == s["id"], model.verification_status == "pending")):
                out.append(
                    {
                        "student_id": s["id"],
                        "student": s["display_name"],
                        "item_type": kind,
                        "item_id": item.id,
                        "title": getattr(item, label),
                    }
                )
    set_rls_subject(db, staff.id)
    return {"items": out}


@router.get("/assessments")
def assessment_catalogue(staff: StaffUser, db: DB) -> dict[str, Any]:
    return {
        "items": [
            {"id": a.id, "slug": a.slug, "name": a.name, "kind": a.kind, "max_score": float(a.max_score)}
            for a in db.scalars(select(Assessment).where(Assessment.is_active.is_(True)))
        ]
    }
