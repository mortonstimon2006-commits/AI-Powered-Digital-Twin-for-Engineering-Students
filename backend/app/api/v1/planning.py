from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Query
from pydantic import Field
from sqlalchemy import select

from app.deps import DB, CurrentUser
from app.errors import AppError, NotFound
from app.models import Roadmap, RoadmapEvent, RoadmapItem
from app.schemas.common import StrictModel
from app.security.ratelimit import EXPENSIVE_USER, limiter
from app.services import audit
from app.services.career import knowledge_graph as kg
from app.services.career.gap_engine import analyse_role
from app.services.career.roadmap import (
    active_or_none,
    compare_roadmaps,
    generate_roadmap,
    owned_roadmap,
    roadmap_view,
)
from app.services.twin.history import estimates_for

router = APIRouter(tags=["planning"])


# ----------------------------------------------------------------------------- knowledge graph


@router.get("/knowledge-graph")
def knowledge_graph(
    principal: CurrentUser,
    db: DB,
    role_id: int | None = Query(default=None),
    include: str = Query(default="resource,assessment,project", max_length=60),
) -> dict[str, Any]:
    limiter.hit(EXPENSIVE_USER, str(principal.id))
    state, catalogue, estimates = estimates_for(db, principal.id)
    role_id = role_id or state.profile.get("target_role_id")
    if role_id is not None and role_id not in catalogue.roles:
        raise NotFound("Role not found.")
    inc = {s.strip() for s in include.split(",") if s.strip() in {"resource", "assessment", "project"}}
    g = kg.student_graph(catalogue, state, estimates)
    match = analyse_role(catalogue.roles[role_id], estimates, catalogue) if role_id else None
    return {"role_id": role_id, **kg.visual_payload(g, role_id=role_id, include=inc, estimates=estimates, match=match)}


@router.get("/knowledge-graph/insights")
def graph_insights(principal: CurrentUser, db: DB, role_id: int | None = Query(default=None)) -> dict[str, Any]:
    state, catalogue, estimates = estimates_for(db, principal.id)
    role_id = role_id or state.profile.get("target_role_id")
    if role_id is None or role_id not in catalogue.roles:
        raise AppError(
            "Choose a target role (or pass role_id) to compute graph insights.", code="target_role_required", status_code=422
        )
    preferred = state.profile.get("preferred_role_ids") or []
    match = analyse_role(
        catalogue.roles[role_id],
        estimates,
        catalogue,
        other_roles=[catalogue.roles[r] for r in preferred if r in catalogue.roles],
    )
    return {
        "role_id": role_id,
        "role_name": catalogue.roles[role_id].name,
        "blocking_prerequisites": kg.blocking_prerequisites(catalogue, estimates, role_id),
        "resources_for_top_gaps": kg.resources_for_top_gaps(catalogue, match),
        "alternative_roles": kg.alternative_roles(catalogue, estimates, role_id),
        "multi_role_unlocks": kg.multi_role_unlocks(catalogue, estimates, preferred if len(preferred) >= 2 else None),
    }


# ----------------------------------------------------------------------------- roadmaps


class GenerateRoadmapIn(StrictModel):
    role_id: int | None = None
    hours_per_week: int | None = Field(default=None, ge=1, le=80)


@router.post("/roadmaps/generate")
def generate(body: GenerateRoadmapIn, principal: CurrentUser, db: DB) -> dict[str, Any]:
    limiter.hit(EXPENSIVE_USER, str(principal.id))
    previous = active_or_none(db, principal.id)
    rm = generate_roadmap(db, principal.id, role_id=body.role_id, hours_per_week=body.hours_per_week)
    audit.record(db, "roadmap.generated", actor_id=principal.id, target_type="roadmap", target_id=rm.id)
    db.commit()
    view = roadmap_view(db, rm)
    if previous is not None:
        view["comparison_with_previous"] = compare_roadmaps(db, previous, rm)
    return view


@router.get("/roadmaps/active")
def get_active(principal: CurrentUser, db: DB) -> dict[str, Any]:
    rm = active_or_none(db, principal.id)
    if rm is None:
        return {"exists": False}
    return {"exists": True, **roadmap_view(db, rm)}


@router.get("/roadmaps")
def list_roadmaps(principal: CurrentUser, db: DB) -> dict[str, Any]:
    rows = db.scalars(select(Roadmap).where(Roadmap.user_id == principal.id).order_by(Roadmap.created_at.desc()).limit(50))
    return {
        "items": [
            {
                "id": r.id,
                "status": r.status,
                "role_id": r.role_id,
                "created_at": r.created_at,
                "archived_at": r.archived_at,
                "hours_per_week": r.hours_per_week,
                "weeks": r.params.get("weeks"),
                "match_at_generation": r.params.get("match"),
            }
            for r in rows
        ]
    }


@router.get("/roadmaps/{roadmap_id}")
def get_roadmap(roadmap_id: uuid.UUID, principal: CurrentUser, db: DB) -> dict[str, Any]:
    return roadmap_view(db, owned_roadmap(db, principal.id, roadmap_id))


@router.get("/roadmaps/{roadmap_id}/compare/{other_id}")
def compare(roadmap_id: uuid.UUID, other_id: uuid.UUID, principal: CurrentUser, db: DB) -> dict[str, Any]:
    old = owned_roadmap(db, principal.id, other_id)
    new = owned_roadmap(db, principal.id, roadmap_id)
    return compare_roadmaps(db, old, new)


class ItemUpdateIn(StrictModel):
    status: Literal["not_started", "in_progress", "completed", "skipped"] | None = None
    note: str | None = Field(default=None, max_length=1000)


def _owned_item(db: DB, user_id: uuid.UUID, item_id: uuid.UUID) -> RoadmapItem:
    item = db.scalar(select(RoadmapItem).where(RoadmapItem.id == item_id, RoadmapItem.user_id == user_id))
    if item is None:
        raise NotFound("Roadmap item not found.")
    return item


@router.patch("/roadmaps/items/{item_id}")
def update_item(item_id: uuid.UUID, body: ItemUpdateIn, principal: CurrentUser, db: DB) -> dict[str, Any]:
    item = _owned_item(db, principal.id, item_id)
    rm = db.get(Roadmap, item.roadmap_id)
    if rm is None or rm.status != "active":
        raise AppError("Only items of the active roadmap can be changed.", code="roadmap_archived", status_code=409)
    if body.status and body.status != item.status:
        db.add(
            RoadmapEvent(
                user_id=principal.id,
                roadmap_id=item.roadmap_id,
                item_id=item.id,
                event="status_changed",
                from_value=item.status,
                to_value=body.status,
            )
        )
        item.status = body.status
        item.completed_at = datetime.now(UTC) if body.status == "completed" else None
    if body.note is not None:
        item.note = body.note
        item.user_edited = True
    db.commit()
    hint = None
    if body.status == "completed":
        hint = (
            "Great progress. Completing an item does not change your skill estimate by itself — link a project "
            "as evidence or ask a mentor to record an assessment."
        )
    return {"id": item.id, "status": item.status, "note": item.note, "evidence_hint": hint}


class ReorderIn(StrictModel):
    item_ids: list[uuid.UUID] = Field(min_length=1, max_length=50)


@router.put("/roadmaps/{roadmap_id}/order")
def reorder(roadmap_id: uuid.UUID, body: ReorderIn, principal: CurrentUser, db: DB) -> dict[str, Any]:
    rm = owned_roadmap(db, principal.id, roadmap_id)
    if rm.status != "active":
        raise AppError("Only the active roadmap can be reordered.", code="roadmap_archived", status_code=409)
    items = {i.id: i for i in db.scalars(select(RoadmapItem).where(RoadmapItem.roadmap_id == rm.id))}
    if set(body.item_ids) != set(items) or len(body.item_ids) != len(items):
        raise AppError("Provide every item of this roadmap exactly once.", code="invalid_order", status_code=422)
    position = {iid: n for n, iid in enumerate(body.item_ids, start=1)}
    by_skill = {i.skill_id: i for i in items.values()}
    warnings = []
    for iid, it in items.items():
        for pid in it.prerequisite_skill_ids:
            pre = by_skill.get(pid)
            if pre is not None and position[pre.id] > position[iid]:
                warnings.append(f"Item {position[iid]} now comes before its prerequisite (item {position[pre.id]}).")
    cumulative = 0.0
    for iid in body.item_ids:
        it = items[iid]
        it.position = position[iid]
        it.user_edited = True
        it.week_start = int(cumulative // rm.hours_per_week) + 1
        cumulative += (it.effort_hours_min + it.effort_hours_max) / 2
        it.week_end = max(it.week_start, -(-int(cumulative) // rm.hours_per_week))
    db.add(RoadmapEvent(user_id=principal.id, roadmap_id=rm.id, event="reordered"))
    db.commit()
    return {**roadmap_view(db, rm), "warnings": warnings}


@router.get("/progress/timeline")
def progress_timeline(principal: CurrentUser, db: DB, limit: int = Query(default=100, ge=1, le=500)) -> dict[str, Any]:
    """Measured history only: snapshots, predictions, roadmap events (no simulations)."""
    from app.models import ModelVersion, Prediction, TwinSnapshot

    snaps = db.scalars(
        select(TwinSnapshot).where(TwinSnapshot.user_id == principal.id).order_by(TwinSnapshot.created_at.desc()).limit(limit)
    ).all()
    preds = db.scalars(
        select(Prediction).where(Prediction.user_id == principal.id).order_by(Prediction.created_at.desc()).limit(limit)
    ).all()
    events = db.scalars(
        select(RoadmapEvent).where(RoadmapEvent.user_id == principal.id).order_by(RoadmapEvent.occurred_at.desc()).limit(limit)
    ).all()
    versions = {m.id: m.version for m in db.scalars(select(ModelVersion))}
    return {
        "snapshots": [
            {"version": s.version, "reason": s.reason, "created_at": s.created_at, "features": s.features}
            for s in reversed(snaps)
        ],
        "predictions": [
            {
                "created_at": p.created_at,
                "band": p.band,
                "probability": p.probability,
                "model_version": versions.get(p.model_version_id),
            }
            for p in reversed(preds)
        ],
        "roadmap_events": [
            {"occurred_at": e.occurred_at, "event": e.event, "from": e.from_value, "to": e.to_value} for e in events
        ],
        "note": (
            "Measured history of your recorded profile. Changes over time are associations; roadmap completion "
            "alongside improved estimates does not by itself show that one caused the other."
        ),
    }
