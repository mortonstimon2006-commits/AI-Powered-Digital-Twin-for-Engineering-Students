"""Personalised, adaptive learning roadmap (deterministic; see docs/methodology/roadmap.md).

Generation:
  1. Gap analysis for the target role (same engine as the gap view).
  2. Take actionable gaps (learn / prerequisite / assess / verify) by priority; expand unmet
     prerequisites in front of the skills they unlock.
  3. Order with a priority-aware topological sort over the prerequisite graph.
  4. Estimate effort from the documented per-level heuristic (LEVEL_HOURS) — a planning range,
     not a measurement — and schedule sequentially against the student's weekly hours.
  5. Attach only catalogue resources (never invented URLs); unverified links are labelled.
Regeneration archives the previous plan, carries over progress for the same skill/action, and
records a diff. Completing an item never raises a skill level by itself — mastery must be
evidenced (project, verified assessment).
"""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime
from typing import Any

import networkx as nx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import AppError, NotFound
from app.models import Roadmap, RoadmapEvent, RoadmapItem, StudentProfile
from app.services.career.gap_engine import SkillGap, analyse_role
from app.services.catalogue import Catalogue, ResourceInfo, load_catalogue
from app.services.twin.proficiency import SkillEstimate
from app.services.twin.state import load_twin_state

GENERATOR_VERSION = "roadmap-v1"
# Planning heuristic: study hours to move INTO level L from L-1 (team estimate, documented).
LEVEL_HOURS = {1: (5, 10), 2: (10, 20), 3: (20, 40), 4: (40, 80)}
ASSESS_HOURS = (2, 4)
VERIFY_HOURS = (4, 10)
MAX_ITEMS = 14


def _effort(action: str, current: float | None, target: int) -> tuple[int, int]:
    if action == "assess":
        return ASSESS_HOURS
    if action == "verify":
        return VERIFY_HOURS
    start = math.floor(current or 0) + 1
    lo = hi = 0
    for lvl in range(start, target + 1):
        a, b = LEVEL_HOURS[lvl]
        lo, hi = lo + a, hi + b
    if current is not None and current > math.floor(current):  # partially into the next level
        frac = current - math.floor(current)
        a, b = LEVEL_HOURS[start]
        lo, hi = lo - int(a * frac), hi - int(b * frac)
    return max(lo, 2), max(hi, 3)


def _pick_resource(catalogue: Catalogue, skill_id: int, current: float | None, target: int) -> ResourceInfo | None:
    options = [catalogue.resources[r] for r in catalogue.resources_by_skill.get(skill_id, [])]
    if not options:
        return None
    nxt = min(math.floor(current or 0) + 1, 4)
    options.sort(
        key=lambda r: (
            not (r.level_min <= nxt <= r.level_max + 1),
            r.verification_status != "verified",
            r.cost != "free",
            abs(r.level_min - nxt),
            r.est_hours_min,
        )
    )
    return options[0]


def _reason(gap: SkillGap, role_name: str, prereq_for: list[str]) -> str:
    lvl = "unknown" if gap.estimated_level is None else f"{gap.estimated_level:g}"
    src = gap.status.replace("_", " ")
    parts = [
        f"{role_name} expects {gap.skill_name} at level {gap.required_level} "
        f"({'core' if gap.is_core else 'optional'}, importance {gap.importance:g}); your current estimate is {lvl}"
        + (f" ({src})." if gap.estimated_level is not None else ".")
    ]
    if gap.blocking_count:
        parts.append(f"It is a prerequisite for {gap.blocking_count} other gap skill(s) in this role.")
    if gap.unlock_count:
        parts.append(f"Also needed for {gap.unlock_count} of your other preferred role(s).")
    if prereq_for:
        parts.append("Needed first for: " + ", ".join(prereq_for) + ".")
    if gap.action == "verify":
        parts.append("Your level meets the requirement but lacks the expected evidence.")
    return " ".join(parts)


def plan_items(
    catalogue: Catalogue, estimates: dict[int, SkillEstimate], role_id: int, hours_per_week: int, preferred_role_ids: list[int]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    role = catalogue.roles[role_id]
    others = [catalogue.roles[r] for r in preferred_role_ids if r in catalogue.roles and r != role_id]
    match = analyse_role(role, estimates, catalogue, other_roles=others)
    actionable = [g for g in match.gaps if g.action in ("learn", "prerequisite", "assess", "verify")]

    chosen: dict[int, dict[str, Any]] = {}
    prereq_for: dict[int, list[str]] = {}

    def add_prereqs(skill_id: int, depth: int = 0) -> None:
        if depth > 6:
            return
        for pid, min_lvl in catalogue.prerequisites.get(skill_id, []):
            pe = estimates[pid]
            if pe.level is not None and pe.level >= min_lvl:
                continue
            prereq_for.setdefault(pid, []).append(catalogue.skills[skill_id].name)
            if pid not in chosen:
                add_prereqs(pid, depth + 1)
                chosen[pid] = {
                    "skill_id": pid,
                    "action": "prerequisite",
                    "current": pe.level,
                    "status": pe.status,
                    "target": min_lvl,
                    "priority": 0.0,
                    "gap": None,
                }

    for g in actionable:
        if len(chosen) >= MAX_ITEMS:
            break
        if g.action in ("learn", "prerequisite"):
            add_prereqs(g.skill_id)
        if g.skill_id in chosen and chosen[g.skill_id]["action"] == "prerequisite":
            chosen[g.skill_id].update(
                action="learn", target=max(chosen[g.skill_id]["target"], g.required_level), priority=g.priority, gap=g
            )
            continue
        if g.skill_id not in chosen:
            chosen[g.skill_id] = {
                "skill_id": g.skill_id,
                "action": "learn" if g.action == "prerequisite" else g.action,
                "current": g.estimated_level,
                "status": g.status,
                "target": g.required_level,
                "priority": g.priority,
                "gap": g,
            }

    # prerequisites inherit the highest priority of what they unlock (so ordering is meaningful)
    for pid, names in prereq_for.items():
        if pid in chosen and chosen[pid]["action"] == "prerequisite":
            dependents = [c["priority"] for c in chosen.values() if catalogue.skills[c["skill_id"]].name in names]
            chosen[pid]["priority"] = max(dependents or [0.0]) + 0.001

    dag = nx.DiGraph()
    dag.add_nodes_from(chosen)
    for sid in chosen:
        for pid, _ in catalogue.prerequisites.get(sid, []):
            if pid in chosen:
                dag.add_edge(pid, sid)
    order = list(nx.lexicographical_topological_sort(dag, key=lambda s: (-chosen[s]["priority"], s)))

    items: list[dict[str, Any]] = []
    cumulative = 0.0
    for pos, sid in enumerate(order[:MAX_ITEMS], start=1):
        c = chosen[sid]
        skill = catalogue.skills[sid]
        lo, hi = _effort(c["action"], c["current"], c["target"])
        mid = (lo + hi) / 2
        week_start = int(cumulative // hours_per_week) + 1
        cumulative += mid
        week_end = max(week_start, math.ceil(cumulative / hours_per_week))
        res = _pick_resource(catalogue, sid, c["current"], c["target"]) if c["action"] != "assess" else None
        gap: SkillGap | None = c["gap"]
        if gap is not None:
            reason = _reason(gap, role.name, prereq_for.get(sid, []))
        else:
            reason = (
                f"Prerequisite: {skill.name} at level {c['target']}+ is needed before "
                f"{', '.join(prereq_for.get(sid, []))}. Current estimate: "
                f"{'unknown' if c['current'] is None else c['current']}."
            )
        if c["action"] == "assess":
            exercise = f"Record a baseline for {skill.name}: rate yourself honestly, then ask a mentor for a short assessment."
            criteria = "A self-rating and, ideally, a mentor-recorded assessment result exist for this skill."
        elif c["action"] == "verify":
            exercise = skill.practice_exercise or f"Produce evidence of your {skill.name} ability."
            criteria = "Evidence is linked (project/experience) or a verified assessment is recorded."
        else:
            exercise = skill.practice_exercise
            criteria = (skill.completion_criteria or "") + " Then link the work as evidence or request an assessment."
        items.append(
            {
                "skill_id": sid,
                "skill_name": skill.name,
                "category": skill.category,
                "position": pos,
                "action": c["action"],
                "priority_score": round(float(c["priority"]), 4),
                "reason": reason,
                "current_level": c["current"],
                "target_level": int(c["target"]),
                "effort_hours_min": lo,
                "effort_hours_max": hi,
                "prerequisite_skill_ids": [p for p, _ in catalogue.prerequisites.get(sid, []) if p in chosen],
                "resource_id": res.id if res else None,
                "exercise": exercise,
                "completion_criteria": criteria.strip(),
                "week_start": week_start,
                "week_end": week_end,
            }
        )
    meta = {
        "role_id": role.id,
        "role_name": role.name,
        "role_version": role.version,
        "match": match.match,
        "total_hours_mid": round(cumulative, 1),
        "weeks": math.ceil(cumulative / hours_per_week) if items else 0,
        "hours_per_week": hours_per_week,
    }
    return items, meta


def _active(db: Session, user_id: uuid.UUID) -> Roadmap | None:
    return db.scalar(select(Roadmap).where(Roadmap.user_id == user_id, Roadmap.status == "active"))


def generate_roadmap(db: Session, user_id: uuid.UUID, *, role_id: int | None, hours_per_week: int | None) -> Roadmap:
    catalogue = load_catalogue(db)
    state = load_twin_state(db, user_id)
    from app.services.twin.proficiency import estimate_skills

    estimates = estimate_skills(state, catalogue)
    profile = db.get(StudentProfile, user_id)
    role_id = role_id or state.profile.get("target_role_id")
    if role_id is None or role_id not in catalogue.roles:
        raise AppError("Choose a target role before generating a roadmap.", code="target_role_required", status_code=422)
    hours = hours_per_week or state.profile.get("weekly_hours") or 8
    items, meta = plan_items(catalogue, estimates, role_id, hours, state.profile.get("preferred_role_ids", []))

    previous = _active(db, user_id)
    carried: dict[tuple[int, str], RoadmapItem] = {}
    if previous is not None:
        for it in db.scalars(select(RoadmapItem).where(RoadmapItem.roadmap_id == previous.id)):
            carried[(it.skill_id, it.action)] = it
        previous.status = "archived"
        previous.archived_at = datetime.now(UTC)
        db.flush()

    rm = Roadmap(
        user_id=user_id,
        role_id=role_id,
        role_version=meta["role_version"],
        hours_per_week=hours,
        generator_version=GENERATOR_VERSION,
        previous_roadmap_id=previous.id if previous else None,
        params={**meta, "twin_version": profile.twin_version if profile else 0, "generated_at": datetime.now(UTC).isoformat()},
    )
    db.add(rm)
    db.flush()
    for planned in items:
        old = carried.get((planned["skill_id"], planned["action"]))
        row = RoadmapItem(
            roadmap_id=rm.id, user_id=user_id, **{k: v for k, v in planned.items() if k not in ("skill_name", "category")}
        )
        if old is not None and old.status in ("in_progress", "completed"):
            row.status, row.completed_at, row.note = old.status, old.completed_at, old.note
        db.add(row)
    db.add(
        RoadmapEvent(
            user_id=user_id,
            roadmap_id=rm.id,
            event="regenerated" if previous else "created",
            from_value=str(previous.id)[:40] if previous else None,
            to_value=str(rm.id)[:40],
        )
    )
    db.flush()
    return rm


def roadmap_view(db: Session, rm: Roadmap) -> dict[str, Any]:
    catalogue = load_catalogue(db)
    items = db.scalars(select(RoadmapItem).where(RoadmapItem.roadmap_id == rm.id).order_by(RoadmapItem.position)).all()
    profile = db.get(StudentProfile, rm.user_id)
    role = catalogue.roles.get(rm.role_id)
    stale_reasons = []
    if profile and profile.twin_version != rm.params.get("twin_version"):
        stale_reasons.append("Your profile changed since this plan was generated.")
    if role and role.version != rm.role_version:
        stale_reasons.append("The role requirements were updated by an administrator.")
    done = sum(1 for i in items if i.status == "completed")
    weeks: dict[int, list[str]] = {}
    out_items = []
    for i in items:
        res = catalogue.resources.get(i.resource_id) if i.resource_id else None
        skill = catalogue.skills.get(i.skill_id)
        out_items.append(
            {
                "id": i.id,
                "position": i.position,
                "skill_id": i.skill_id,
                "skill_name": skill.name if skill else "?",
                "category": skill.category if skill else None,
                "action": i.action,
                "priority_score": i.priority_score,
                "reason": i.reason,
                "current_level": i.current_level,
                "target_level": i.target_level,
                "effort_hours": [i.effort_hours_min, i.effort_hours_max],
                "prerequisites": [catalogue.skills[p].name for p in i.prerequisite_skill_ids if p in catalogue.skills],
                "resource": (
                    {
                        "id": res.id,
                        "title": res.title,
                        "provider": res.provider,
                        "url": res.url,
                        "verification_status": res.verification_status,
                        "cost": res.cost,
                        "est_hours": [res.est_hours_min, res.est_hours_max],
                    }
                    if res
                    else None
                ),
                "exercise": i.exercise,
                "completion_criteria": i.completion_criteria,
                "status": i.status,
                "week_start": i.week_start,
                "week_end": i.week_end,
                "user_edited": i.user_edited,
                "note": i.note,
                "completed_at": i.completed_at,
            }
        )
        for w in range(i.week_start, i.week_end + 1):
            weeks.setdefault(w, []).append(str(i.id))
    return {
        "id": rm.id,
        "status": rm.status,
        "role_id": rm.role_id,
        "role_name": role.name if role else None,
        "role_version": rm.role_version,
        "hours_per_week": rm.hours_per_week,
        "generator_version": rm.generator_version,
        "created_at": rm.created_at,
        "previous_roadmap_id": rm.previous_roadmap_id,
        "params": rm.params,
        "progress": {"completed": done, "total": len(items), "share": round(done / len(items), 3) if items else 0},
        "stale": bool(stale_reasons),
        "stale_reasons": stale_reasons,
        "items": out_items,
        "weeks": [{"week": w, "item_ids": ids} for w, ids in sorted(weeks.items())],
        "months": [
            {"month": m, "weeks": list(range((m - 1) * 4 + 1, m * 4 + 1))}
            for m in range(1, math.ceil((max(weeks) if weeks else 0) / 4) + 1)
        ],
        "disclaimer": (
            "Effort ranges are planning estimates. Completing a resource does not prove mastery — "
            "link evidence or request an assessment to update your twin."
        ),
    }


def compare_roadmaps(db: Session, old: Roadmap, new: Roadmap) -> dict[str, Any]:
    catalogue = load_catalogue(db)

    def items(rm: Roadmap) -> dict[tuple[int, str], RoadmapItem]:
        return {(i.skill_id, i.action): i for i in db.scalars(select(RoadmapItem).where(RoadmapItem.roadmap_id == rm.id))}

    a, b = items(old), items(new)
    name = lambda k: catalogue.skills[k[0]].name if k[0] in catalogue.skills else "?"  # noqa: E731
    return {
        "added": [{"skill": name(k), "action": k[1]} for k in b.keys() - a.keys()],
        "removed": [{"skill": name(k), "action": k[1]} for k in a.keys() - b.keys()],
        "moved": [
            {"skill": name(k), "action": k[1], "from": a[k].position, "to": b[k].position}
            for k in a.keys() & b.keys()
            if a[k].position != b[k].position
        ],
        "carried_progress": [
            {"skill": name(k), "status": b[k].status} for k in a.keys() & b.keys() if b[k].status != "not_started"
        ],
    }


def owned_roadmap(db: Session, user_id: uuid.UUID, roadmap_id: uuid.UUID) -> Roadmap:
    rm = db.scalar(select(Roadmap).where(Roadmap.id == roadmap_id, Roadmap.user_id == user_id))
    if rm is None:
        raise NotFound("Roadmap not found.")
    return rm


def active_or_none(db: Session, user_id: uuid.UUID) -> Roadmap | None:
    return _active(db, user_id)
