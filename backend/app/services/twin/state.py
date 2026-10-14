"""Canonical, serialisable state of one student's digital twin.

`TwinState` is a plain-data snapshot loaded from the database. Everything downstream
(proficiency estimation, ML features, role matching, gaps, simulation) is a pure function of
it, which guarantees the what-if simulator applies *exactly* the same logic to a hypothetical
copy as to the real profile.
"""

from __future__ import annotations

import copy
import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Assessment,
    AssessmentResult,
    Certification,
    Experience,
    Project,
    SkillEvidence,
    StudentProfile,
    StudentRolePreference,
    StudentSkill,
)


@dataclass
class EvidenceItem:
    skill_id: int
    level: int
    source_type: str  # project | experience | certification | hypothetical
    source_id: str
    source_title: str
    verification_status: str
    hypothetical: bool = False


@dataclass
class AssessmentItem:
    assessment_id: int
    kind: str
    pct: float
    taken_on: str
    verification_status: str
    source: str
    hypothetical: bool = False


@dataclass
class ProjectItem:
    id: str
    title: str
    is_deployed: bool
    verification_status: str
    hypothetical: bool = False


@dataclass
class ExperienceItem:
    id: str
    kind: str
    title: str
    organization: str
    months: float
    verification_status: str
    hypothetical: bool = False


@dataclass
class CertificationItem:
    id: str
    name: str
    issuer: str
    verification_status: str
    hypothetical: bool = False


@dataclass
class TwinState:
    user_id: str
    profile: dict[str, Any]
    self_ratings: dict[int, int] = field(default_factory=dict)
    evidence: list[EvidenceItem] = field(default_factory=list)
    assessments: list[AssessmentItem] = field(default_factory=list)
    projects: list[ProjectItem] = field(default_factory=list)
    experiences: list[ExperienceItem] = field(default_factory=list)
    certifications: list[CertificationItem] = field(default_factory=list)
    # Hypothetical skill levels injected by the simulator (skill_id -> level). Never persisted.
    hypothetical_levels: dict[int, float] = field(default_factory=dict)

    def clone(self) -> TwinState:
        return copy.deepcopy(self)

    def to_json(self) -> dict[str, Any]:
        d = asdict(self)
        d["self_ratings"] = {str(k): v for k, v in sorted(self.self_ratings.items())}
        d["hypothetical_levels"] = {str(k): v for k, v in sorted(self.hypothetical_levels.items())}
        return d

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> TwinState:
        return cls(
            user_id=d["user_id"],
            profile=d["profile"],
            self_ratings={int(k): int(v) for k, v in d.get("self_ratings", {}).items()},
            evidence=[EvidenceItem(**e) for e in d.get("evidence", [])],
            assessments=[AssessmentItem(**a) for a in d.get("assessments", [])],
            projects=[ProjectItem(**p) for p in d.get("projects", [])],
            experiences=[ExperienceItem(**e) for e in d.get("experiences", [])],
            certifications=[CertificationItem(**c) for c in d.get("certifications", [])],
            hypothetical_levels={int(k): float(v) for k, v in d.get("hypothetical_levels", {}).items()},
        )

    def content_hash(self) -> str:
        payload = json.dumps(self.to_json(), sort_keys=True, default=str).encode()
        return hashlib.sha256(payload).hexdigest()


def _months_between(start: date, end: date | None, today: date) -> float:
    end = end or today
    days = max((end - start).days, 0)
    return round(days / 30.4375, 1)


def load_twin_state(db: Session, user_id: uuid.UUID, *, today: date | None = None) -> TwinState:
    """Loads one student's twin. Every query filters on user_id explicitly (RLS is the
    second line of defence, not the first)."""
    today = today or date.today()
    p = db.get(StudentProfile, user_id)
    prefs = db.scalars(
        select(StudentRolePreference).where(StudentRolePreference.user_id == user_id).order_by(StudentRolePreference.rank)
    ).all()
    profile = {
        "degree": p.degree if p else None,
        "specialization": p.specialization if p else None,
        "current_semester": p.current_semester if p else None,
        "graduation_year": p.graduation_year if p else None,
        "cgpa": float(p.cgpa) if p and p.cgpa is not None else None,
        "attendance_pct": float(p.attendance_pct) if p and p.attendance_pct is not None else None,
        "career_interests": list(p.career_interests) if p else [],
        "learning_preferences": list(p.learning_preferences) if p else [],
        "weekly_hours": p.weekly_hours if p else 8,
        "target_role_id": p.target_role_id if p else None,
        "preferred_role_ids": [r.role_id for r in prefs],
        "headline": p.headline if p else "",
        "academic_achievements": p.academic_achievements if p else "",
    }
    state = TwinState(user_id=str(user_id), profile=profile)
    state.self_ratings = {
        s.skill_id: s.self_rating for s in db.scalars(select(StudentSkill).where(StudentSkill.user_id == user_id))
    }

    projects = {pr.id: pr for pr in db.scalars(select(Project).where(Project.user_id == user_id))}
    experiences = {e.id: e for e in db.scalars(select(Experience).where(Experience.user_id == user_id))}
    certs = {c.id: c for c in db.scalars(select(Certification).where(Certification.user_id == user_id))}
    state.projects = [
        ProjectItem(str(pr.id), pr.title, pr.is_deployed, pr.verification_status)
        for pr in sorted(projects.values(), key=lambda x: str(x.id))
    ]
    state.experiences = [
        ExperienceItem(
            str(e.id), e.kind, e.title, e.organization, _months_between(e.start_date, e.end_date, today), e.verification_status
        )
        for e in sorted(experiences.values(), key=lambda x: str(x.id))
    ]
    state.certifications = [
        CertificationItem(str(c.id), c.name, c.issuer, c.verification_status)
        for c in sorted(certs.values(), key=lambda x: str(x.id))
    ]

    for ev in db.scalars(select(SkillEvidence).where(SkillEvidence.user_id == user_id).order_by(SkillEvidence.id)):
        if ev.source_type == "project" and ev.project_id in projects:
            src = projects[ev.project_id]
            title, status, sid = src.title, src.verification_status, ev.project_id
        elif ev.source_type == "experience" and ev.experience_id in experiences:
            src_e = experiences[ev.experience_id]
            title, status, sid = f"{src_e.title} @ {src_e.organization}", src_e.verification_status, ev.experience_id
        elif ev.source_type == "certification" and ev.certification_id in certs:
            src_c = certs[ev.certification_id]
            title, status, sid = src_c.name, src_c.verification_status, ev.certification_id
        else:
            continue
        state.evidence.append(EvidenceItem(ev.skill_id, ev.level_demonstrated, ev.source_type, str(sid), title, status))

    rows = db.execute(
        select(AssessmentResult, Assessment.kind)
        .join(Assessment, Assessment.id == AssessmentResult.assessment_id)
        .where(AssessmentResult.user_id == user_id)
        .order_by(AssessmentResult.taken_on, AssessmentResult.id)
    ).all()
    state.assessments = [
        AssessmentItem(
            r.assessment_id,
            kind,
            round(float(r.score) / float(r.max_score) * 100, 1),
            r.taken_on.isoformat(),
            r.verification_status,
            r.source,
        )
        for r, kind in rows
    ]
    return state
