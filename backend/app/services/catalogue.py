"""Read-side catalogue access with a process-local cache keyed by a catalogue fingerprint.
The cache holds ONLY global reference data (never student data), so it cannot leak data
between users."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Assessment,
    AssessmentSkill,
    CareerRole,
    LearningResource,
    ResourceSkill,
    RoleSkillRequirement,
    RoleVersion,
    Skill,
    SkillPrerequisite,
)


@dataclass(frozen=True)
class SkillInfo:
    id: int
    slug: str
    name: str
    category: str
    kind: str
    description: str
    aliases: tuple[str, ...]
    practice_exercise: str
    completion_criteria: str


@dataclass(frozen=True)
class Requirement:
    skill_id: int
    required_level: int
    importance: float
    is_core: bool
    evidence_expected: str
    alt_group: str | None
    rationale: str


@dataclass(frozen=True)
class RoleInfo:
    id: int
    slug: str
    name: str
    summary: str
    description: str
    version: int
    source_note: str
    requirements: tuple[Requirement, ...]


@dataclass(frozen=True)
class ResourceInfo:
    id: int
    title: str
    provider: str
    url: str
    resource_type: str
    cost: str
    level_min: int
    level_max: int
    est_hours_min: int
    est_hours_max: int
    verification_status: str
    skill_ids: tuple[int, ...]


@dataclass
class Catalogue:
    fingerprint: str
    skills: dict[int, SkillInfo]
    roles: dict[int, RoleInfo]
    prerequisites: dict[int, list[tuple[int, int]]]  # skill_id -> [(prereq_id, min_level)]
    resources: dict[int, ResourceInfo]
    resources_by_skill: dict[int, list[int]]
    assessments: dict[int, dict[str, Any]]
    assessment_skills: dict[int, list[int]]  # assessment_id -> skill_ids
    by_slug: dict[str, int] = field(default_factory=dict)
    role_by_slug: dict[str, int] = field(default_factory=dict)


_cache: dict[str, Catalogue] = {}
_lock = threading.Lock()


def _fingerprint(db: Session) -> str:
    parts = [
        db.scalar(select(func.count(Skill.id))),
        db.scalar(select(func.max(Skill.updated_at))),
        db.scalar(select(func.sum(CareerRole.version))),
        db.scalar(select(func.max(CareerRole.updated_at))),
        db.scalar(select(func.count()).select_from(SkillPrerequisite)),
        db.scalar(select(func.count(LearningResource.id))),
        db.scalar(select(func.max(LearningResource.last_checked_at))),
        db.scalar(select(func.count()).select_from(ResourceSkill)),
        db.scalar(select(func.count(Assessment.id))),
        db.scalar(select(func.count()).select_from(RoleSkillRequirement)),
    ]
    return "|".join(str(p) for p in parts)


def load_catalogue(db: Session) -> Catalogue:
    fp = _fingerprint(db)
    with _lock:
        cached = _cache.get("current")
        if cached and cached.fingerprint == fp:
            return cached
    skills = {
        s.id: SkillInfo(
            s.id, s.slug, s.name, s.category, s.kind, s.description, tuple(s.aliases), s.practice_exercise, s.completion_criteria
        )
        for s in db.scalars(select(Skill).where(Skill.is_active.is_(True)))
    }
    roles: dict[int, RoleInfo] = {}
    for r in db.scalars(select(CareerRole).where(CareerRole.is_active.is_(True)).order_by(CareerRole.name)):
        reqs = tuple(
            Requirement(q.skill_id, q.required_level, q.importance, q.is_core, q.evidence_expected, q.alt_group, q.rationale)
            for q in sorted(r.requirements, key=lambda q: (-q.importance, q.skill_id))
            if q.skill_id in skills
        )
        roles[r.id] = RoleInfo(r.id, r.slug, r.name, r.summary, r.description, r.version, r.source_note, reqs)
    prereqs: dict[int, list[tuple[int, int]]] = {}
    for p in db.scalars(select(SkillPrerequisite)):
        prereqs.setdefault(p.skill_id, []).append((p.prerequisite_id, p.min_level))
    res_skills: dict[int, list[int]] = {}
    for rs in db.scalars(select(ResourceSkill)):
        res_skills.setdefault(rs.resource_id, []).append(rs.skill_id)
    resources = {
        r.id: ResourceInfo(
            r.id,
            r.title,
            r.provider,
            r.url,
            r.resource_type,
            r.cost,
            r.level_min,
            r.level_max,
            r.est_hours_min,
            r.est_hours_max,
            r.verification_status,
            tuple(res_skills.get(r.id, ())),
        )
        for r in db.scalars(
            select(LearningResource).where(LearningResource.is_active.is_(True), LearningResource.verification_status != "broken")
        )
    }
    by_skill: dict[int, list[int]] = {}
    for rid, info in resources.items():
        for sid in info.skill_ids:
            by_skill.setdefault(sid, []).append(rid)
    assessments = {
        a.id: {
            "id": a.id,
            "slug": a.slug,
            "name": a.name,
            "kind": a.kind,
            "max_score": float(a.max_score),
            "description": a.description,
        }
        for a in db.scalars(select(Assessment).where(Assessment.is_active.is_(True)))
    }
    a_skills: dict[int, list[int]] = {}
    for link in db.scalars(select(AssessmentSkill)):
        a_skills.setdefault(link.assessment_id, []).append(link.skill_id)
    cat = Catalogue(
        fp,
        skills,
        roles,
        prereqs,
        resources,
        by_skill,
        assessments,
        a_skills,
        by_slug={s.slug: s.id for s in skills.values()},
        role_by_slug={r.slug: r.id for r in roles.values()},
    )
    with _lock:
        _cache["current"] = cat
    return cat


def role_spec(role: CareerRole) -> dict[str, Any]:
    return {
        "slug": role.slug,
        "name": role.name,
        "summary": role.summary,
        "description": role.description,
        "version": role.version,
        "source_note": role.source_note,
        "requirements": [
            {
                "skill_id": q.skill_id,
                "required_level": q.required_level,
                "importance": q.importance,
                "is_core": q.is_core,
                "evidence_expected": q.evidence_expected,
                "alt_group": q.alt_group,
                "rationale": q.rationale,
            }
            for q in sorted(role.requirements, key=lambda q: q.skill_id)
        ],
    }


def snapshot_role_version(db: Session, role: CareerRole, created_by: uuid.UUID | None) -> None:
    db.add(RoleVersion(role_id=role.id, version=role.version, spec=role_spec(role), created_by=created_by))
