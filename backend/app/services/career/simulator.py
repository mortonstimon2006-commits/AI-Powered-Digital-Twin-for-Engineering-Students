"""What-if career simulator.

1. Load the student's ACTUAL twin state.            4. Recompute estimates/features with the SAME code.
2. Clone it (deep copy — the real twin is untouched). 5. Re-run the SAME versioned model + gap engine.
3. Apply only the requested, validated changes.      6. Return baseline vs hypothetical with limitations.

Results are associations under the current model and framework. They do not establish that
the real-world action would cause an equivalent change in employability.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import Field, model_validator
from sqlalchemy.orm import Session

from app.errors import AppError
from app.ml.feature_schema import FEATURE_BY_NAME
from app.schemas.common import StrictModel
from app.services.career.gap_engine import analyse_role
from app.services.career.readiness import predict
from app.services.catalogue import Catalogue, load_catalogue
from app.services.twin.features import build_features
from app.services.twin.proficiency import estimate_skills
from app.services.twin.state import (
    AssessmentItem,
    CertificationItem,
    EvidenceItem,
    ExperienceItem,
    ProjectItem,
    TwinState,
    load_twin_state,
)

KIND_TO_ASSESSMENT_KIND = {"coding": "coding", "communication": "communication", "mock_interview": "mock_interview"}


class SkillChange(StrictModel):
    skill_id: int
    level: float = Field(ge=0, le=4)
    basis: Literal["assessed", "project_evidence"] = "assessed"


class AssessmentChange(StrictModel):
    kind: Literal["coding", "communication", "mock_interview"]
    pct: float = Field(ge=0, le=100)


class ScenarioChanges(StrictModel):
    skill_levels: list[SkillChange] = Field(default_factory=list, max_length=20)
    add_projects: int = Field(default=0, ge=0, le=10)
    add_deployed_projects: int = Field(default=0, ge=0, le=10)
    add_internship_months: float = Field(default=0, ge=0, le=24)
    add_verified_certifications: int = Field(default=0, ge=0, le=10)
    add_hackathons: int = Field(default=0, ge=0, le=10)
    assessments: list[AssessmentChange] = Field(default_factory=list, max_length=3)
    cgpa: float | None = Field(default=None, ge=0, le=10)
    semester: int | None = Field(default=None, ge=1, le=12)

    @model_validator(mode="after")
    def _consistent(self) -> ScenarioChanges:
        if len({s.skill_id for s in self.skill_levels}) != len(self.skill_levels):
            raise ValueError("each skill may be changed once per scenario")
        if len({a.kind for a in self.assessments}) != len(self.assessments):
            raise ValueError("each assessment kind may be set once per scenario")
        if self.add_deployed_projects > self.add_projects:
            raise ValueError("add_deployed_projects cannot exceed add_projects")
        return self

    def is_empty(self) -> bool:
        return self == ScenarioChanges()


class SimulationRequest(StrictModel):
    changes: ScenarioChanges
    role_ids: list[int] = Field(default_factory=list, max_length=4)


def apply_changes(
    base: TwinState, changes: ScenarioChanges, catalogue: Catalogue
) -> tuple[TwinState, list[dict[str, Any]], list[str]]:
    state = base.clone()
    applied: list[dict[str, Any]] = []
    plausibility: list[str] = []
    base_est = estimate_skills(base, catalogue)

    for sc in changes.skill_levels:
        if sc.skill_id not in catalogue.skills:
            raise AppError(f"Unknown skill id {sc.skill_id}.", code="invalid_skill", status_code=422)
        name = catalogue.skills[sc.skill_id].name
        before = base_est[sc.skill_id].level
        if sc.basis == "assessed":
            state.hypothetical_levels[sc.skill_id] = sc.level
        else:
            state.evidence.append(
                EvidenceItem(
                    sc.skill_id,
                    round(sc.level) or 1,
                    "hypothetical",
                    "sim",
                    "Hypothetical project",
                    "verified",
                    hypothetical=True,
                )
            )
        applied.append({"type": "skill_level", "skill": name, "before": before, "after": sc.level, "basis": sc.basis})
        if before is not None and sc.level - before >= 2:
            plausibility.append(f"{name}: a jump of {sc.level - before:g} levels usually takes several months of work.")

    for i in range(changes.add_projects):
        state.projects.append(
            ProjectItem(
                f"sim-project-{i}",
                f"Hypothetical project {i + 1}",
                i < changes.add_deployed_projects,
                "unverified",
                hypothetical=True,
            )
        )
    if changes.add_projects:
        applied.append({"type": "projects", "added": changes.add_projects, "deployed": changes.add_deployed_projects})
    if changes.add_internship_months:
        state.experiences.append(
            ExperienceItem(
                "sim-internship",
                "internship",
                "Hypothetical internship",
                "—",
                changes.add_internship_months,
                "unverified",
                hypothetical=True,
            )
        )
        applied.append({"type": "internship_months", "added": changes.add_internship_months})
    for i in range(changes.add_verified_certifications):
        state.certifications.append(
            CertificationItem(f"sim-cert-{i}", "Hypothetical certification", "—", "verified", hypothetical=True)
        )
    if changes.add_verified_certifications:
        applied.append({"type": "verified_certifications", "added": changes.add_verified_certifications})
    for i in range(changes.add_hackathons):
        state.experiences.append(
            ExperienceItem(f"sim-hack-{i}", "hackathon", "Hypothetical hackathon", "—", 0.1, "unverified", hypothetical=True)
        )
    if changes.add_hackathons:
        applied.append({"type": "hackathons", "added": changes.add_hackathons})

    kind_to_id: dict[str, int] = {}
    for assessment_id, a in catalogue.assessments.items():
        kind_to_id.setdefault(a["kind"], assessment_id)
    for ac in changes.assessments:
        aid = kind_to_id.get(KIND_TO_ASSESSMENT_KIND[ac.kind])
        if aid is None:
            raise AppError(
                f"No assessment of kind {ac.kind} exists in the catalogue.", code="invalid_assessment", status_code=422
            )
        state.assessments.append(AssessmentItem(aid, ac.kind, ac.pct, "9999-12-31", "verified", "simulation", hypothetical=True))
        applied.append({"type": "assessment", "kind": ac.kind, "pct": ac.pct})

    if changes.cgpa is not None:
        before_cgpa = base.profile.get("cgpa")
        state.profile["cgpa"] = changes.cgpa
        applied.append({"type": "cgpa", "before": before_cgpa, "after": changes.cgpa})
        if before_cgpa is not None and abs(changes.cgpa - before_cgpa) > 1.0:
            plausibility.append("CGPA rarely changes by more than 1.0 point within a year.")
    if changes.semester is not None:
        before_sem = base.profile.get("current_semester")
        if before_sem is not None and changes.semester < before_sem:
            raise AppError("A scenario cannot move to an earlier semester.", code="invalid_change", status_code=422)
        state.profile["current_semester"] = changes.semester
        applied.append({"type": "semester", "before": before_sem, "after": changes.semester})
    return state, applied, plausibility


def _readiness(features: dict[str, float | None]) -> dict[str, Any]:
    r = predict(features)
    if not r.get("available"):
        return {"available": False, "reason": r.get("reason_unavailable")}
    return {
        k: r[k]
        for k in (
            "available",
            "model_version",
            "is_synthetic_model",
            "band",
            "band_label",
            "probability",
            "calibrated_score",
            "calibration_validated",
            "known_input_share",
            "warnings",
        )
    } | {"top_factors": r["explanation"]["top"][:5]}


def simulate(db: Session, user_id: uuid.UUID, request: SimulationRequest) -> dict[str, Any]:
    if request.changes.is_empty():
        raise AppError("Choose at least one hypothetical change.", code="empty_scenario", status_code=422)
    catalogue = load_catalogue(db)
    baseline = load_twin_state(db, user_id)
    hypothetical, applied, plausibility = apply_changes(baseline, request.changes, catalogue)

    base_est = estimate_skills(baseline, catalogue)
    hyp_est = estimate_skills(hypothetical, catalogue)
    base_f = build_features(baseline, catalogue, base_est)  # same validation as the real model path
    hyp_f = build_features(hypothetical, catalogue, hyp_est)

    role_ids = request.role_ids or [
        r for r in (baseline.profile.get("target_role_id"), *baseline.profile.get("preferred_role_ids", [])) if r
    ]
    role_ids = list(dict.fromkeys(role_ids))[:4] or list(catalogue.roles)[:3]
    roles = []
    for rid in role_ids:
        role = catalogue.roles.get(rid)
        if role is None:
            raise AppError(f"Unknown role id {rid}.", code="invalid_role", status_code=422)
        b = analyse_role(role, base_est, catalogue)
        h = analyse_role(role, hyp_est, catalogue)
        b_gaps = {g.skill_id: g for g in b.gaps}
        changed_gaps = []
        for g in h.gaps:
            bg = b_gaps.get(g.skill_id)
            if bg and (bg.estimated_level != g.estimated_level or bg.action != g.action):
                changed_gaps.append(
                    {
                        "skill": g.skill_name,
                        "before_level": bg.estimated_level,
                        "after_level": g.estimated_level,
                        "before_action": bg.action,
                        "after_action": g.action,
                        "required_level": g.required_level,
                    }
                )
        roles.append(
            {
                "role_id": rid,
                "role_name": role.name,
                "role_version": role.version,
                "baseline": {
                    "match": b.match,
                    "match_upper": b.match_upper,
                    "gap_count": b.gap_count,
                    "unknown_count": b.unknown_count,
                },
                "hypothetical": {
                    "match": h.match,
                    "match_upper": h.match_upper,
                    "gap_count": h.gap_count,
                    "unknown_count": h.unknown_count,
                },
                "delta_match": round(h.match - b.match, 4),
                "changed_skills": changed_gaps,
                "top_remaining_gaps": [
                    {"skill": g.skill_name, "action": g.action, "gap": g.gap}
                    for g in h.gaps
                    if g.action in ("learn", "prerequisite", "assess")
                ][:5],
            }
        )

    feature_changes = [
        {"feature": k, "label": FEATURE_BY_NAME[k].label, "before": base_f[k], "after": hyp_f[k]}
        for k in base_f
        if base_f[k] != hyp_f[k]
    ]
    return {
        "hypothetical": True,
        "changes_applied": applied,
        "plausibility_notes": plausibility,
        "feature_changes": feature_changes,
        "readiness": {"baseline": _readiness(base_f), "hypothetical": _readiness(hyp_f)},
        "roles": roles,
        "limitations": [
            "HYPOTHETICAL: nothing here has been saved to your profile.",
            "Differences are what the current model and role framework compute for these inputs; they do not prove "
            "that taking the action would cause the same change in real employability.",
            "Hypothetical assessments and skill levels are treated as verified evidence; real ones must be earned.",
        ],
    }
