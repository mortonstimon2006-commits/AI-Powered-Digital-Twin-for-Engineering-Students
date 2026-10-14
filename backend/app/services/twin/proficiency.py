"""Evidence-aware skill proficiency estimation (pure functions).

Each skill's estimate comes from the HIGHEST-TRUST source available (documented in
docs/methodology/proficiency.md):

    assessed            verified assessment results mapped to the skill   trust 1.00
    verified_evidence   evidence attached to a verified project/experience/certificate   0.85
    unverified_evidence evidence attached to an unverified/pending source  0.60
    self_reported       the student's own rating                           0.40
    unknown             no information — NOT zero proficiency               0.00

Lower-trust signals are still returned (for transparency) but do not override higher-trust
ones. Hypothetical (simulated) signals are tagged and never stored.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.catalogue import Catalogue
from app.services.twin.state import TwinState

TRUST = {
    "assessed": 1.0,
    "verified_evidence": 0.85,
    "unverified_evidence": 0.6,
    "self_reported": 0.4,
    "unknown": 0.0,
}
STATUS_ORDER = ["assessed", "verified_evidence", "unverified_evidence", "self_reported"]


def pct_to_level(pct: float) -> float:
    """Documented linear mapping from an assessment percentage to the 0–4 scale
    (25 percentage points per level). A heuristic, not a psychometric calibration."""
    return round(max(0.0, min(4.0, pct / 25.0)), 2)


@dataclass
class SkillEstimate:
    skill_id: int
    level: float | None
    status: str
    trust: float
    hypothetical: bool = False
    signals: list[dict[str, Any]] = field(default_factory=list)

    @property
    def known(self) -> bool:
        return self.level is not None


def estimate_skills(state: TwinState, catalogue: Catalogue) -> dict[int, SkillEstimate]:
    signals: dict[int, dict[str, list[dict[str, Any]]]] = {}

    def add(skill_id: int, status: str, level: float, detail: dict[str, Any]) -> None:
        if skill_id not in catalogue.skills:
            return
        signals.setdefault(skill_id, {}).setdefault(status, []).append({"level": level, **detail})

    # Assessments: latest VERIFIED result per assessment, mapped to each measured skill.
    latest: dict[int, Any] = {}
    for a in state.assessments:
        if a.verification_status != "verified":
            continue
        prev = latest.get(a.assessment_id)
        if prev is None or (a.taken_on, a.hypothetical) >= (prev.taken_on, prev.hypothetical):
            latest[a.assessment_id] = a
    for a in latest.values():
        for sid in catalogue.assessment_skills.get(a.assessment_id, []):
            add(
                sid,
                "assessed",
                pct_to_level(a.pct),
                {
                    "source": "assessment",
                    "assessment": catalogue.assessments.get(a.assessment_id, {}).get("name"),
                    "pct": a.pct,
                    "taken_on": a.taken_on,
                    "hypothetical": a.hypothetical,
                },
            )

    for ev in state.evidence:
        if ev.verification_status == "rejected":
            continue
        status = "verified_evidence" if ev.verification_status == "verified" else "unverified_evidence"
        add(
            ev.skill_id,
            status,
            float(ev.level),
            {
                "source": ev.source_type,
                "title": ev.source_title,
                "verification": ev.verification_status,
                "hypothetical": ev.hypothetical,
            },
        )

    for sid, rating in state.self_ratings.items():
        add(sid, "self_reported", float(rating), {"source": "self_rating", "hypothetical": False})

    for sid, lvl in state.hypothetical_levels.items():
        # Simulator: "what if this skill were assessed at level X" — highest trust, flagged.
        add(sid, "assessed", float(lvl), {"source": "simulation", "hypothetical": True})

    estimates: dict[int, SkillEstimate] = {}
    for sid in catalogue.skills:
        by_status = signals.get(sid, {})
        for status in STATUS_ORDER:
            items = by_status.get(status)
            if not items:
                continue
            if status == "assessed":
                hyp = [i for i in items if i.get("hypothetical")]
                chosen = hyp if hyp else items
                level = sum(i["level"] for i in chosen) / len(chosen)
            else:
                level = max(i["level"] for i in items)
            all_signals = [{"status": st, **i} for st in STATUS_ORDER for i in by_status.get(st, [])]
            estimates[sid] = SkillEstimate(
                skill_id=sid,
                level=round(level, 2),
                status=status,
                trust=TRUST[status],
                hypothetical=any(i.get("hypothetical") for i in items),
                signals=all_signals,
            )
            break
        else:
            estimates[sid] = SkillEstimate(skill_id=sid, level=None, status="unknown", trust=0.0)
    return estimates
