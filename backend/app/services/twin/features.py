"""Twin state -> ML feature vector (pure). Must stay consistent with
app/ml/feature_schema.py and the training pipeline's documented semantics."""

from __future__ import annotations

import math

from app.ml.feature_schema import CATEGORY_FEATURES, FEATURE_NAMES, validate_vector
from app.services.catalogue import Catalogue
from app.services.twin.proficiency import SkillEstimate, estimate_skills
from app.services.twin.state import TwinState

STRONG = {"assessed", "verified_evidence"}


def _latest_verified_pct(state: TwinState, kind: str) -> float | None:
    rows = [a for a in state.assessments if a.kind == kind and a.verification_status == "verified"]
    if not rows:
        return None
    rows.sort(key=lambda a: (a.taken_on, a.hypothetical))
    return float(rows[-1].pct)


def build_features(
    state: TwinState, catalogue: Catalogue, estimates: dict[int, SkillEstimate] | None = None
) -> dict[str, float | None]:
    est = estimates if estimates is not None else estimate_skills(state, catalogue)
    f: dict[str, float | None] = {}
    f["cgpa"] = state.profile.get("cgpa")
    f["semester"] = state.profile.get("current_semester")

    known = [e for e in est.values() if e.known]
    for cat in CATEGORY_FEATURES:
        levels = [e.level for e in known if catalogue.skills[e.skill_id].category == cat and e.level is not None]
        f[f"lvl_{cat}"] = round(sum(levels) / len(levels), 3) if levels else None
    f["evidence_strength"] = round(sum(1 for e in known if e.status in STRONG) / len(known), 3) if known else None

    f["projects"] = float(len(state.projects))
    f["deployed_projects"] = float(sum(1 for p in state.projects if p.is_deployed))
    f["internship_months"] = round(min(sum(e.months for e in state.experiences if e.kind in ("internship", "job")), 60.0), 1)
    f["certifications_verified"] = float(sum(1 for c in state.certifications if c.verification_status == "verified"))
    f["hackathons"] = float(sum(1 for e in state.experiences if e.kind == "hackathon"))
    f["coding_assessment_pct"] = _latest_verified_pct(state, "coding")
    f["communication_pct"] = _latest_verified_pct(state, "communication")
    f["mock_interview_pct"] = _latest_verified_pct(state, "mock_interview")

    # Clip counts to the schema maxima (documented saturation) and validate.
    for name in ("projects", "deployed_projects", "certifications_verified", "hackathons"):
        f[name] = min(f[name] or 0.0, 40.0)
    problems = validate_vector(f)
    if problems:
        raise ValueError("invalid feature vector: " + "; ".join(problems))
    assert tuple(f) == FEATURE_NAMES
    return f


def known_share(features: dict[str, float | None]) -> float:
    vals = list(features.values())
    return sum(1 for v in vals if v is not None and not (isinstance(v, float) and math.isnan(v))) / len(vals)
