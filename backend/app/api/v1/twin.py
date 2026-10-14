"""Digital-twin endpoints. Every query is filtered by the authenticated user's id (never an id
from the client); RLS enforces the same boundary in the database. Each meaningful change
creates a content-addressed snapshot for longitudinal history."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Query, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.deps import DB, CurrentUser
from app.errors import AppError, NotFound
from app.models import (
    Assessment,
    AssessmentResult,
    CareerRole,
    Certification,
    Consent,
    Experience,
    Project,
    SkillEvidence,
    StudentProfile,
    StudentRolePreference,
    StudentSkill,
    TwinSnapshot,
)
from app.schemas.common import Message
from app.schemas.twin import (
    AssessmentResultOut,
    BulkSkillRatingsIn,
    CertificationIn,
    CertificationOut,
    EvidenceLinkIn,
    EvidenceOut,
    ExperienceIn,
    ExperienceOut,
    ProfileIn,
    ProfileOut,
    ProjectIn,
    ProjectOut,
    RolePreferencesIn,
    SelfReportedAssessmentIn,
    SkillRatingIn,
    VerificationRequestIn,
)
from app.services import audit
from app.services.catalogue import load_catalogue
from app.services.twin.history import completeness, diff_states, ensure_snapshot, estimates_for, feature_deltas

router = APIRouter(tags=["digital-twin"])


def _profile(db: Session, user_id: uuid.UUID) -> StudentProfile:
    p = db.get(StudentProfile, user_id)
    if p is None:
        p = StudentProfile(user_id=user_id)
        db.add(p)
        db.flush()
    return p


def _has_consent(db: Session, user_id: uuid.UUID, purpose: str) -> bool:
    c = db.get(Consent, (user_id, purpose))
    return bool(c and c.granted)


def _profile_out(db: Session, p: StudentProfile) -> ProfileOut:
    prefs = db.scalars(
        select(StudentRolePreference.role_id)
        .where(StudentRolePreference.user_id == p.user_id)
        .order_by(StudentRolePreference.rank)
    ).all()
    return ProfileOut(
        degree=p.degree,
        specialization=p.specialization,
        current_semester=p.current_semester,
        graduation_year=p.graduation_year,
        cgpa=float(p.cgpa) if p.cgpa is not None else None,
        attendance_pct=float(p.attendance_pct) if p.attendance_pct is not None else None,
        academic_achievements=p.academic_achievements,
        headline=p.headline,
        career_interests=list(p.career_interests),
        learning_preferences=list(p.learning_preferences),
        weekly_hours=p.weekly_hours,
        target_role_id=p.target_role_id,
        preferred_role_ids=list(prefs),
        twin_version=p.twin_version,
        onboarding_completed_at=p.onboarding_completed_at,
        attendance_consent=_has_consent(db, p.user_id, "attendance_data"),
    )


def _commit_change(db: Session, user_id: uuid.UUID, reason: str) -> None:
    ensure_snapshot(db, user_id, reason)
    db.commit()


# ----------------------------------------------------------------------------- profile


@router.get("/profile", response_model=ProfileOut)
def get_profile(principal: CurrentUser, db: DB) -> ProfileOut:
    return _profile_out(db, _profile(db, principal.id))


@router.put("/profile", response_model=ProfileOut)
def update_profile(body: ProfileIn, principal: CurrentUser, db: DB) -> ProfileOut:
    p = _profile(db, principal.id)
    data = body.model_dump()
    if data.get("attendance_pct") is not None and not _has_consent(db, principal.id, "attendance_data"):
        raise AppError(
            "Grant the attendance-data consent in Privacy settings before storing attendance.",
            code="consent_required",
            status_code=403,
        )
    for key, value in data.items():
        setattr(p, key, value)
    _commit_change(db, principal.id, "profile_updated")
    return _profile_out(db, p)


@router.patch("/profile", response_model=ProfileOut)
def patch_profile(body: ProfileIn, principal: CurrentUser, db: DB) -> ProfileOut:
    """Partial update: only fields present in the request body change."""
    p = _profile(db, principal.id)
    data = body.model_dump(exclude_unset=True)
    if data.get("attendance_pct") is not None and not _has_consent(db, principal.id, "attendance_data"):
        raise AppError(
            "Grant the attendance-data consent in Privacy settings before storing attendance.",
            code="consent_required",
            status_code=403,
        )
    for key, value in data.items():
        setattr(p, key, value)
    _commit_change(db, principal.id, "profile_updated")
    return _profile_out(db, p)


@router.put("/profile/roles", response_model=ProfileOut)
def update_role_preferences(body: RolePreferencesIn, principal: CurrentUser, db: DB) -> ProfileOut:
    ids = set(body.preferred_role_ids) | ({body.target_role_id} if body.target_role_id else set())
    if ids:
        found = set(db.scalars(select(CareerRole.id).where(CareerRole.id.in_(ids), CareerRole.is_active.is_(True))))
        if found != ids:
            raise AppError("One or more roles do not exist.", code="invalid_role", status_code=422)
    p = _profile(db, principal.id)
    p.target_role_id = body.target_role_id
    db.execute(delete(StudentRolePreference).where(StudentRolePreference.user_id == principal.id))
    ordered = [body.target_role_id] if body.target_role_id else []
    ordered += [r for r in body.preferred_role_ids if r != body.target_role_id]
    for rank, rid in enumerate(ordered[:5], start=1):
        db.add(StudentRolePreference(user_id=principal.id, role_id=rid, rank=rank))
    _commit_change(db, principal.id, "role_preferences_updated")
    return _profile_out(db, p)


@router.post("/profile/onboarding/complete", response_model=ProfileOut)
def complete_onboarding(principal: CurrentUser, db: DB) -> ProfileOut:
    p = _profile(db, principal.id)
    if p.target_role_id is None:
        raise AppError("Choose a target role to finish onboarding.", code="onboarding_incomplete", status_code=422)
    p.onboarding_completed_at = p.onboarding_completed_at or datetime.now(UTC)
    _commit_change(db, principal.id, "onboarding_completed")
    return _profile_out(db, p)


# ----------------------------------------------------------------------------- skills


@router.get("/twin/skills")
def list_skills(principal: CurrentUser, db: DB, category: str | None = Query(default=None, max_length=24)) -> dict[str, Any]:
    state, catalogue, estimates = estimates_for(db, principal.id)
    items = []
    for sid, skill in sorted(catalogue.skills.items(), key=lambda kv: (kv[1].category, kv[1].name)):
        if category and skill.category != category:
            continue
        e = estimates[sid]
        items.append(
            {
                "skill_id": sid,
                "slug": skill.slug,
                "name": skill.name,
                "category": skill.category,
                "kind": skill.kind,
                "description": skill.description,
                "self_rating": state.self_ratings.get(sid),
                "estimated_level": e.level,
                "status": e.status,
                "trust": e.trust,
                "signals": e.signals,
            }
        )
    return {"items": items, "proficiency_scale": _scale()}


def _scale() -> list[dict[str, Any]]:
    from app.seed.catalogue_data import PROFICIENCY_LEVELS

    return [{"level": k, "name": v[0], "description": v[1]} for k, v in PROFICIENCY_LEVELS.items()]


def _check_skill_ids(db: Session, ids: set[int]) -> None:
    catalogue = load_catalogue(db)
    unknown = ids - set(catalogue.skills)
    if unknown:
        raise AppError(f"Unknown skill id(s): {sorted(unknown)}", code="invalid_skill", status_code=422)


@router.put("/twin/skills/{skill_id}", response_model=Message)
def rate_skill(skill_id: int, body: SkillRatingIn, principal: CurrentUser, db: DB) -> Message:
    _check_skill_ids(db, {skill_id})
    row = db.scalar(select(StudentSkill).where(StudentSkill.user_id == principal.id, StudentSkill.skill_id == skill_id))
    if row is None:
        db.add(StudentSkill(user_id=principal.id, skill_id=skill_id, self_rating=body.self_rating, source="manual"))
    else:
        row.self_rating = body.self_rating
        row.source = "manual"
    _commit_change(db, principal.id, "skill_rated")
    return Message(message="Skill rating saved.")


@router.put("/twin/skills", response_model=Message)
def rate_skills_bulk(body: BulkSkillRatingsIn, principal: CurrentUser, db: DB) -> Message:
    ids = [r.skill_id for r in body.ratings]
    if len(set(ids)) != len(ids):
        raise AppError("Each skill may appear only once.", code="duplicate_skill", status_code=422)
    _check_skill_ids(db, set(ids))
    existing = {s.skill_id: s for s in db.scalars(select(StudentSkill).where(StudentSkill.user_id == principal.id))}
    for r in body.ratings:
        if r.skill_id in existing:
            existing[r.skill_id].self_rating = r.self_rating
            existing[r.skill_id].source = body.source
        else:
            db.add(StudentSkill(user_id=principal.id, skill_id=r.skill_id, self_rating=r.self_rating, source=body.source))
    _commit_change(db, principal.id, f"skills_rated_{body.source}")
    return Message(message=f"Saved {len(body.ratings)} skill rating(s).")


@router.delete("/twin/skills/{skill_id}", response_model=Message)
def clear_skill_rating(skill_id: int, principal: CurrentUser, db: DB) -> Message:
    res = db.execute(delete(StudentSkill).where(StudentSkill.user_id == principal.id, StudentSkill.skill_id == skill_id))
    if not res.rowcount:  # type: ignore[attr-defined]
        raise NotFound("No rating for this skill.")
    _commit_change(db, principal.id, "skill_rating_cleared")
    return Message(message="Rating removed; the skill is now 'unknown'.")


# ----------------------------------------------------------------------------- evidence helpers


def _replace_evidence(
    db: Session, user_id: uuid.UUID, links: list[EvidenceLinkIn], *, source_type: str, source_id: uuid.UUID
) -> None:
    _check_skill_ids(db, {lk.skill_id for lk in links})
    if len({lk.skill_id for lk in links}) != len(links):
        raise AppError("Each skill may be linked only once per item.", code="duplicate_skill", status_code=422)
    col = {
        "project": SkillEvidence.project_id,
        "experience": SkillEvidence.experience_id,
        "certification": SkillEvidence.certification_id,
    }[source_type]
    db.execute(delete(SkillEvidence).where(SkillEvidence.user_id == user_id, col == source_id))
    for lk in links:
        db.add(
            SkillEvidence(
                user_id=user_id,
                skill_id=lk.skill_id,
                source_type=source_type,
                level_demonstrated=lk.level,
                note=lk.note,
                **{f"{source_type}_id": source_id},
            )
        )


def _evidence_for(db: Session, user_id: uuid.UUID, source_type: str) -> dict[uuid.UUID, list[EvidenceOut]]:
    col = {
        "project": SkillEvidence.project_id,
        "experience": SkillEvidence.experience_id,
        "certification": SkillEvidence.certification_id,
    }[source_type]
    out: dict[uuid.UUID, list[EvidenceOut]] = {}
    for ev in db.scalars(select(SkillEvidence).where(SkillEvidence.user_id == user_id, SkillEvidence.source_type == source_type)):
        out.setdefault(getattr(ev, f"{source_type}_id"), []).append(
            EvidenceOut(id=ev.id, skill_id=ev.skill_id, level_demonstrated=ev.level_demonstrated, note=ev.note)
        )
    _ = col
    return out


def _owned(db: Session, model: Any, item_id: uuid.UUID, user_id: uuid.UUID) -> Any:
    obj = db.scalar(select(model).where(model.id == item_id, model.user_id == user_id))
    if obj is None:  # same response whether it doesn't exist or belongs to someone else
        raise NotFound("Item not found.")
    return obj


# ----------------------------------------------------------------------------- projects


@router.get("/twin/projects", response_model=list[ProjectOut])
def list_projects(principal: CurrentUser, db: DB) -> list[ProjectOut]:
    ev = _evidence_for(db, principal.id, "project")
    rows = db.scalars(select(Project).where(Project.user_id == principal.id).order_by(Project.created_at.desc()))
    return [ProjectOut.model_validate(p).model_copy(update={"skills": ev.get(p.id, [])}) for p in rows]


@router.post("/twin/projects", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(body: ProjectIn, principal: CurrentUser, db: DB) -> ProjectOut:
    count = len(db.scalars(select(Project.id).where(Project.user_id == principal.id)).all())
    if count >= 40:
        raise AppError("Project limit reached (40).", code="limit_reached", status_code=422)
    p = Project(user_id=principal.id, **body.model_dump(exclude={"skills"}))
    db.add(p)
    db.flush()
    _replace_evidence(db, principal.id, body.skills, source_type="project", source_id=p.id)
    _commit_change(db, principal.id, "project_added")
    return ProjectOut.model_validate(p).model_copy(update={"skills": _evidence_for(db, principal.id, "project").get(p.id, [])})


@router.put("/twin/projects/{project_id}", response_model=ProjectOut)
def update_project(project_id: uuid.UUID, body: ProjectIn, principal: CurrentUser, db: DB) -> ProjectOut:
    p = _owned(db, Project, project_id, principal.id)
    data = body.model_dump(exclude={"skills"})
    substantive = any(getattr(p, k) != v for k, v in data.items() if k in ("title", "summary", "repo_url", "demo_url"))
    for k, v in data.items():
        setattr(p, k, v)
    if substantive and p.verification_status == "verified":
        # Verification applied to the old content; edited claims must be re-verified.
        p.verification_status, p.verified_by, p.verified_at = "unverified", None, None
    _replace_evidence(db, principal.id, body.skills, source_type="project", source_id=p.id)
    _commit_change(db, principal.id, "project_updated")
    return ProjectOut.model_validate(p).model_copy(update={"skills": _evidence_for(db, principal.id, "project").get(p.id, [])})


@router.delete("/twin/projects/{project_id}", response_model=Message)
def delete_project(project_id: uuid.UUID, principal: CurrentUser, db: DB) -> Message:
    db.delete(_owned(db, Project, project_id, principal.id))
    _commit_change(db, principal.id, "project_removed")
    return Message(message="Project deleted.")


# ----------------------------------------------------------------------------- experiences


@router.get("/twin/experiences", response_model=list[ExperienceOut])
def list_experiences(principal: CurrentUser, db: DB) -> list[ExperienceOut]:
    ev = _evidence_for(db, principal.id, "experience")
    rows = db.scalars(select(Experience).where(Experience.user_id == principal.id).order_by(Experience.start_date.desc()))
    return [ExperienceOut.model_validate(e).model_copy(update={"skills": ev.get(e.id, [])}) for e in rows]


@router.post("/twin/experiences", response_model=ExperienceOut, status_code=status.HTTP_201_CREATED)
def create_experience(body: ExperienceIn, principal: CurrentUser, db: DB) -> ExperienceOut:
    e = Experience(user_id=principal.id, **body.model_dump(exclude={"skills"}))
    db.add(e)
    db.flush()
    _replace_evidence(db, principal.id, body.skills, source_type="experience", source_id=e.id)
    _commit_change(db, principal.id, "experience_added")
    return ExperienceOut.model_validate(e).model_copy(
        update={"skills": _evidence_for(db, principal.id, "experience").get(e.id, [])}
    )


@router.put("/twin/experiences/{experience_id}", response_model=ExperienceOut)
def update_experience(experience_id: uuid.UUID, body: ExperienceIn, principal: CurrentUser, db: DB) -> ExperienceOut:
    e = _owned(db, Experience, experience_id, principal.id)
    data = body.model_dump(exclude={"skills"})
    substantive = any(getattr(e, k) != v for k, v in data.items() if k in ("organization", "title", "start_date", "end_date"))
    for k, v in data.items():
        setattr(e, k, v)
    if substantive and e.verification_status == "verified":
        e.verification_status, e.verified_by, e.verified_at = "unverified", None, None
    _replace_evidence(db, principal.id, body.skills, source_type="experience", source_id=e.id)
    _commit_change(db, principal.id, "experience_updated")
    return ExperienceOut.model_validate(e).model_copy(
        update={"skills": _evidence_for(db, principal.id, "experience").get(e.id, [])}
    )


@router.delete("/twin/experiences/{experience_id}", response_model=Message)
def delete_experience(experience_id: uuid.UUID, principal: CurrentUser, db: DB) -> Message:
    db.delete(_owned(db, Experience, experience_id, principal.id))
    _commit_change(db, principal.id, "experience_removed")
    return Message(message="Experience deleted.")


# ----------------------------------------------------------------------------- certifications


@router.get("/twin/certifications", response_model=list[CertificationOut])
def list_certifications(principal: CurrentUser, db: DB) -> list[CertificationOut]:
    ev = _evidence_for(db, principal.id, "certification")
    rows = db.scalars(
        select(Certification).where(Certification.user_id == principal.id).order_by(Certification.created_at.desc())
    )
    return [CertificationOut.model_validate(c).model_copy(update={"skills": ev.get(c.id, [])}) for c in rows]


@router.post("/twin/certifications", response_model=CertificationOut, status_code=status.HTTP_201_CREATED)
def create_certification(body: CertificationIn, principal: CurrentUser, db: DB) -> CertificationOut:
    c = Certification(user_id=principal.id, **body.model_dump(exclude={"skills"}))
    db.add(c)
    db.flush()
    _replace_evidence(db, principal.id, body.skills, source_type="certification", source_id=c.id)
    _commit_change(db, principal.id, "certification_added")
    return CertificationOut.model_validate(c).model_copy(
        update={"skills": _evidence_for(db, principal.id, "certification").get(c.id, [])}
    )


@router.delete("/twin/certifications/{certification_id}", response_model=Message)
def delete_certification(certification_id: uuid.UUID, principal: CurrentUser, db: DB) -> Message:
    db.delete(_owned(db, Certification, certification_id, principal.id))
    _commit_change(db, principal.id, "certification_removed")
    return Message(message="Certification deleted.")


# ----------------------------------------------------------------------------- assessments


def _assessment_out(r: AssessmentResult, a: Assessment) -> AssessmentResultOut:
    return AssessmentResultOut(
        id=r.id,
        assessment_id=a.id,
        assessment_name=a.name,
        kind=a.kind,
        score=float(r.score),
        max_score=float(r.max_score),
        pct=round(float(r.score) / float(r.max_score) * 100, 1),
        taken_on=r.taken_on,
        source=r.source,
        verification_status=r.verification_status,
        notes=r.notes,
    )


@router.get("/twin/assessments")
def list_assessment_results(principal: CurrentUser, db: DB) -> dict[str, Any]:
    rows = db.execute(
        select(AssessmentResult, Assessment)
        .join(Assessment, Assessment.id == AssessmentResult.assessment_id)
        .where(AssessmentResult.user_id == principal.id)
        .order_by(AssessmentResult.taken_on.desc())
    ).all()
    catalogue = load_catalogue(db)
    return {
        "results": [_assessment_out(r, a) for r, a in rows],
        "catalogue": [
            {
                **a,
                "skills": [
                    catalogue.skills[s].name for s in catalogue.assessment_skills.get(a["id"], []) if s in catalogue.skills
                ],
            }
            for a in catalogue.assessments.values()
        ],
    }


@router.post("/twin/assessments", response_model=AssessmentResultOut, status_code=status.HTTP_201_CREATED)
def add_self_reported_assessment(body: SelfReportedAssessmentIn, principal: CurrentUser, db: DB) -> AssessmentResultOut:
    a = db.get(Assessment, body.assessment_id)
    if a is None or not a.is_active:
        raise AppError("Unknown assessment.", code="invalid_assessment", status_code=422)
    if body.score > float(a.max_score):
        raise AppError(f"Score cannot exceed {float(a.max_score):g}.", code="invalid_score", status_code=422)
    r = AssessmentResult(
        user_id=principal.id,
        assessment_id=a.id,
        score=body.score,
        max_score=a.max_score,
        taken_on=body.taken_on,
        source="self_reported",
        verification_status="unverified",
        notes=body.notes,
    )
    db.add(r)
    db.flush()
    _commit_change(db, principal.id, "assessment_self_reported")
    return _assessment_out(r, a)


@router.delete("/twin/assessments/{result_id}", response_model=Message)
def delete_self_reported_assessment(result_id: uuid.UUID, principal: CurrentUser, db: DB) -> Message:
    r = _owned(db, AssessmentResult, result_id, principal.id)
    if r.source != "self_reported":
        raise AppError("Assessor-recorded results can only be removed by staff.", code="forbidden", status_code=403)
    db.delete(r)
    _commit_change(db, principal.id, "assessment_removed")
    return Message(message="Result deleted.")


@router.post("/twin/verification-requests", response_model=Message)
def request_verification(body: VerificationRequestIn, principal: CurrentUser, db: DB) -> Message:
    model = {"project": Project, "experience": Experience, "certification": Certification, "assessment": AssessmentResult}[
        body.item_type
    ]
    item = _owned(db, model, body.item_id, principal.id)
    if item.verification_status in ("verified", "pending"):
        raise AppError(f"Item is already {item.verification_status}.", code="invalid_state", status_code=409)
    item.verification_status = "pending"
    audit.record(db, "twin.verification.requested", actor_id=principal.id, target_type=body.item_type, target_id=body.item_id)
    _commit_change(db, principal.id, "verification_requested")
    return Message(message="Verification requested. A mentor will review it.")


# ----------------------------------------------------------------------------- history / summary


@router.get("/twin/snapshots")
def list_snapshots(
    principal: CurrentUser, db: DB, limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0)
) -> dict[str, Any]:
    rows = db.scalars(
        select(TwinSnapshot)
        .where(TwinSnapshot.user_id == principal.id)
        .order_by(TwinSnapshot.version.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return {
        "items": [
            {"id": s.id, "version": s.version, "reason": s.reason, "created_at": s.created_at, "features": s.features}
            for s in rows
        ],
        "limit": limit,
        "offset": offset,
    }


@router.get("/twin/diff")
def diff_snapshots(
    principal: CurrentUser, db: DB, from_version: int = Query(ge=1), to_version: int | None = Query(default=None, ge=1)
) -> dict[str, Any]:
    def get(v: int | None) -> TwinSnapshot:
        stmt = select(TwinSnapshot).where(TwinSnapshot.user_id == principal.id)
        stmt = stmt.where(TwinSnapshot.version == v) if v else stmt.order_by(TwinSnapshot.version.desc()).limit(1)
        snap = db.scalar(stmt)
        if snap is None:
            raise NotFound("Snapshot not found.")
        return snap

    old, new = get(from_version), get(to_version)
    catalogue = load_catalogue(db)
    return {
        "from": {"version": old.version, "created_at": old.created_at},
        "to": {"version": new.version, "created_at": new.created_at},
        "changes": diff_states(old.state, new.state, catalogue),
        "feature_changes": feature_deltas(old.features, new.features),
    }


@router.get("/twin/completeness")
def get_completeness(principal: CurrentUser, db: DB) -> dict[str, Any]:
    state, _, estimates = estimates_for(db, principal.id)
    return completeness(state, estimates)
