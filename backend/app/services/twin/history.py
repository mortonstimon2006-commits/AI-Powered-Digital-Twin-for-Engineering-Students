"""Versioned twin snapshots, profile completeness and human-readable change history."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import StudentProfile, TwinSnapshot
from app.services.catalogue import Catalogue, load_catalogue
from app.services.twin.features import build_features
from app.services.twin.proficiency import SkillEstimate, estimate_skills
from app.services.twin.state import TwinState, load_twin_state


def ensure_snapshot(db: Session, user_id: uuid.UUID, reason: str) -> TwinSnapshot:
    """Creates a new snapshot iff the twin's content changed since the latest one."""
    catalogue = load_catalogue(db)
    state = load_twin_state(db, user_id)
    digest = state.content_hash()
    latest = db.scalar(select(TwinSnapshot).where(TwinSnapshot.user_id == user_id).order_by(TwinSnapshot.version.desc()).limit(1))
    if latest is not None and latest.content_hash == digest:
        return latest
    features = build_features(state, catalogue)
    snap = TwinSnapshot(
        user_id=user_id,
        version=(latest.version + 1) if latest else 1,
        reason=reason[:64],
        content_hash=digest,
        state=state.to_json(),
        features=features,
    )
    db.add(snap)
    profile = db.get(StudentProfile, user_id)
    if profile is not None:
        profile.twin_version = snap.version
    db.flush()
    return snap


def latest_snapshot(db: Session, user_id: uuid.UUID) -> TwinSnapshot | None:
    return db.scalar(select(TwinSnapshot).where(TwinSnapshot.user_id == user_id).order_by(TwinSnapshot.version.desc()).limit(1))


# ----------------------------------------------------------------------------- completeness

SECTIONS = (
    ("academic", 0.20, "Academic details"),
    ("goals", 0.15, "Career goals"),
    ("skills", 0.20, "Skill self-assessment"),
    ("evidence", 0.20, "Practical evidence"),
    ("assessments", 0.15, "Verified assessments"),
    ("preferences", 0.10, "Learning preferences"),
)


def completeness(state: TwinState, estimates: dict[int, SkillEstimate]) -> dict[str, Any]:
    p = state.profile
    academic_fields = ["degree", "specialization", "current_semester", "graduation_year", "cgpa"]
    academic = sum(1 for f in academic_fields if p.get(f) not in (None, "")) / len(academic_fields)
    goals = (0.6 if p.get("target_role_id") else 0.0) + (0.4 if p.get("career_interests") else 0.0)
    rated = len(state.self_ratings)
    skills = min(rated / 8, 1.0)
    evidence = (
        min((len(state.projects) * 0.5 + min(len(state.evidence), 6) / 6 * 0.5), 1.0)
        if state.projects
        else (min(len(state.evidence), 6) / 12)
    )
    verified_assess = sum(1 for a in state.assessments if a.verification_status == "verified")
    assessments = min(verified_assess / 2, 1.0)
    prefs = (0.5 if p.get("learning_preferences") else 0.0) + (0.5 if p.get("weekly_hours") else 0.0)
    scores = {
        "academic": academic,
        "goals": goals,
        "skills": skills,
        "evidence": evidence,
        "assessments": assessments,
        "preferences": prefs,
    }
    hints = {
        "academic": "Add degree, specialization, semester, graduation year and CGPA.",
        "goals": "Choose a target role and add career interests.",
        "skills": f"Rate at least 8 skills (you have rated {rated}).",
        "evidence": "Add projects or experience and link the skills they demonstrate.",
        "assessments": "Ask a mentor to record assessment results (verified evidence is weighted highest).",
        "preferences": "Set your weekly study hours and learning preferences.",
    }
    sections = [
        {
            "key": key,
            "label": label,
            "weight": weight,
            "score": round(scores[key], 3),
            "complete": scores[key] >= 0.999,
            "hint": None if scores[key] >= 0.999 else hints[key],
        }
        for key, weight, label in SECTIONS
    ]
    overall = sum(weight * scores[key] for key, weight, _ in SECTIONS)
    known = sum(1 for e in estimates.values() if e.known)
    return {
        "overall": round(overall, 3),
        "sections": sections,
        "known_skills": known,
        "rated_skills": rated,
        "verified_assessments": verified_assess,
    }


# ----------------------------------------------------------------------------- diffs


def diff_states(old: dict[str, Any], new: dict[str, Any], catalogue: Catalogue) -> list[dict[str, Any]]:
    """Human-readable list of meaningful changes between two serialised twin states."""
    changes: list[dict[str, Any]] = []
    name = lambda sid: catalogue.skills[int(sid)].name if int(sid) in catalogue.skills else f"skill {sid}"  # noqa: E731
    for field, before in old.get("profile", {}).items():
        after = new.get("profile", {}).get(field)
        if before != after:
            changes.append({"kind": "profile", "field": field, "before": before, "after": after})
    o_r, n_r = old.get("self_ratings", {}), new.get("self_ratings", {})
    for sid in sorted(set(o_r) | set(n_r), key=int):
        if o_r.get(sid) != n_r.get(sid):
            changes.append({"kind": "self_rating", "skill": name(sid), "before": o_r.get(sid), "after": n_r.get(sid)})

    def keyed(items: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
        return {str(i[key]): i for i in items}

    for collection, key, label in (("projects", "id", "title"), ("experiences", "id", "title"), ("certifications", "id", "name")):
        o, n = keyed(old.get(collection, []), key), keyed(new.get(collection, []), key)
        for k in n.keys() - o.keys():
            changes.append({"kind": f"{collection[:-1]}_added", "title": n[k][label]})
        for k in o.keys() - n.keys():
            changes.append({"kind": f"{collection[:-1]}_removed", "title": o[k][label]})
        for k in n.keys() & o.keys():
            if o[k].get("verification_status") != n[k].get("verification_status"):
                changes.append(
                    {
                        "kind": f"{collection[:-1]}_verification",
                        "title": n[k][label],
                        "before": o[k].get("verification_status"),
                        "after": n[k].get("verification_status"),
                    }
                )
    ev_key = lambda e: (e["skill_id"], e["source_type"], e["source_id"])  # noqa: E731
    o_ev = {ev_key(e): e for e in old.get("evidence", [])}
    n_ev = {ev_key(e): e for e in new.get("evidence", [])}
    for ek in n_ev.keys() - o_ev.keys():
        changes.append(
            {"kind": "evidence_added", "skill": name(ek[0]), "source": n_ev[ek]["source_title"], "level": n_ev[ek]["level"]}
        )
    for ek in o_ev.keys() - n_ev.keys():
        changes.append({"kind": "evidence_removed", "skill": name(ek[0]), "source": o_ev[ek]["source_title"]})
    o_a = {(a["assessment_id"], a["taken_on"], a["pct"]) for a in old.get("assessments", [])}
    for a in new.get("assessments", []):
        if (a["assessment_id"], a["taken_on"], a["pct"]) not in o_a:
            changes.append(
                {
                    "kind": "assessment_added",
                    "assessment": catalogue.assessments.get(a["assessment_id"], {}).get("name"),
                    "pct": a["pct"],
                    "verification": a["verification_status"],
                }
            )
    return changes


def feature_deltas(old: dict[str, Any], new: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for k, after in new.items():
        before = old.get(k)
        if before != after:
            out.append({"feature": k, "before": before, "after": after})
    return out


def estimates_for(db: Session, user_id: uuid.UUID) -> tuple[TwinState, Catalogue, dict[int, SkillEstimate]]:
    catalogue = load_catalogue(db)
    state = load_twin_state(db, user_id)
    return state, catalogue, estimate_skills(state, catalogue)
