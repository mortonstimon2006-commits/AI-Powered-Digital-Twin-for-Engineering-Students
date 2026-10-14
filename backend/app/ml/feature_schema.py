"""The single feature contract shared by dataset building, training, inference, SHAP and the
what-if simulator. Changing it requires retraining (the schema hash is stored in every model
manifest and checked at load time).

Missing values are meaningful: NaN = "unknown / not assessed", never zero.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

CATEGORY_FEATURES = ("programming", "dsa", "databases", "web", "ml_ai", "data", "cloud_devops", "security")
CATEGORY_LABELS = {
    "programming": "Programming",
    "dsa": "DSA",
    "databases": "Databases",
    "web": "Web development",
    "ml_ai": "AI/ML",
    "data": "Data analysis",
    "cloud_devops": "Cloud/DevOps",
    "security": "Security",
    "professional": "Professional skills",
}


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    label: str
    minimum: float
    maximum: float
    unit: str
    description: str
    integer: bool = False


FEATURES: tuple[FeatureSpec, ...] = (
    FeatureSpec("cgpa", "CGPA", 0, 10, "/10", "Cumulative grade point average on a 10-point scale."),
    FeatureSpec("semester", "Semester", 1, 12, "", "Current semester of study.", integer=True),
    *(
        FeatureSpec(
            f"lvl_{c}",
            f"{CATEGORY_LABELS[c]} level",
            0,
            4,
            "/4",
            f"Evidence-weighted proficiency across rated '{c}' skills (best estimate per skill, averaged).",
        )
        for c in CATEGORY_FEATURES
    ),
    FeatureSpec(
        "evidence_strength",
        "Evidence strength",
        0,
        1,
        "",
        "Share of rated skills backed by verified evidence or assessments rather than self-rating only.",
    ),
    FeatureSpec("projects", "Projects", 0, 40, "", "Number of recorded projects.", integer=True),
    FeatureSpec("deployed_projects", "Deployed projects", 0, 40, "", "Projects marked as deployed.", integer=True),
    FeatureSpec("internship_months", "Internship months", 0, 60, "months", "Total months of internship/job experience."),
    FeatureSpec(
        "certifications_verified",
        "Verified certifications",
        0,
        40,
        "",
        "Certifications with verification status 'verified'.",
        integer=True,
    ),
    FeatureSpec("hackathons", "Hackathons", 0, 40, "", "Hackathon participations recorded.", integer=True),
    FeatureSpec(
        "coding_assessment_pct", "Coding assessment", 0, 100, "%", "Latest verified coding-assessment score as a percentage."
    ),
    FeatureSpec(
        "communication_pct",
        "Communication assessment",
        0,
        100,
        "%",
        "Latest verified communication assessment score as a percentage.",
    ),
    FeatureSpec("mock_interview_pct", "Mock interview", 0, 100, "%", "Latest verified mock-interview score as a percentage."),
)

FEATURE_NAMES: tuple[str, ...] = tuple(f.name for f in FEATURES)
FEATURE_BY_NAME: dict[str, FeatureSpec] = {f.name: f for f in FEATURES}

TARGET_NAME = "assessor_interview_ready"
TARGET_DEFINITION = (
    "Binary label recorded by a qualified assessor (mentor/faculty) after a structured review: "
    "1 = the student is judged ready to interview for an entry-level technical role, 0 = not yet. "
    "It is NOT a placement or hiring outcome and must not be presented as one."
)


def schema_hash() -> str:
    payload = json.dumps([asdict(f) for f in FEATURES], sort_keys=True).encode()
    return hashlib.sha256(payload).hexdigest()[:16]


def validate_vector(values: dict[str, float | None]) -> list[str]:
    """Returns human-readable problems; empty list = valid. Unknown keys are rejected."""
    problems = [f"unknown feature '{k}'" for k in values if k not in FEATURE_BY_NAME]
    for spec in FEATURES:
        v = values.get(spec.name)
        if v is None:
            continue
        if not isinstance(v, int | float) or v != v:  # NaN check
            problems.append(f"{spec.name}: not a number")
            continue
        if v < spec.minimum or v > spec.maximum:
            problems.append(f"{spec.name}: {v} outside [{spec.minimum}, {spec.maximum}]")
        if spec.integer and float(v) != int(v):
            problems.append(f"{spec.name}: must be a whole number")
    return problems
