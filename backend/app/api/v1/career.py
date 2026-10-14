from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Query, status
from pydantic import Field
from sqlalchemy import select

from app.deps import DB, CurrentUser, OptionalUser
from app.errors import AppError, NotFound
from app.ml.feature_schema import FEATURES, TARGET_DEFINITION
from app.ml.registry import registry
from app.models import ModelVersion, Prediction, TwinSnapshot, WhatIfScenario
from app.schemas.common import Message, StrictModel
from app.security.ratelimit import EXPENSIVE_USER, SIMULATION_USER, limiter
from app.seed.catalogue_data import FRAMEWORK_SOURCE_NOTE, PROFICIENCY_LEVELS
from app.services import audit
from app.services.career.gap_engine import GapConfig, analyse_all_roles, analyse_role, ranking_sensitivity
from app.services.career.readiness import predict, prediction_history, store_prediction
from app.services.career.simulator import SimulationRequest, simulate
from app.services.catalogue import load_catalogue
from app.services.twin.features import build_features
from app.services.twin.history import ensure_snapshot, estimates_for, latest_snapshot

router = APIRouter(tags=["career-intelligence"])


# ----------------------------------------------------------------------------- roles (public catalogue)


def _role_summary(role: Any, catalogue: Any) -> dict[str, Any]:
    return {
        "id": role.id,
        "slug": role.slug,
        "name": role.name,
        "summary": role.summary,
        "description": role.description,
        "version": role.version,
        "source_note": role.source_note,
        "requirements": [
            {
                "skill_id": q.skill_id,
                "skill_slug": catalogue.skills[q.skill_id].slug,
                "skill_name": catalogue.skills[q.skill_id].name,
                "category": catalogue.skills[q.skill_id].category,
                "required_level": q.required_level,
                "importance": q.importance,
                "is_core": q.is_core,
                "evidence_expected": q.evidence_expected,
                "alt_group": q.alt_group,
                "rationale": q.rationale,
            }
            for q in role.requirements
        ],
    }


@router.get("/roles")
def list_roles(db: DB, _principal: OptionalUser) -> dict[str, Any]:
    """Public: the role-skill framework is reference data, not personal data."""
    catalogue = load_catalogue(db)
    return {
        "framework_note": FRAMEWORK_SOURCE_NOTE,
        "proficiency_scale": [{"level": k, "name": v[0], "description": v[1]} for k, v in PROFICIENCY_LEVELS.items()],
        "roles": [_role_summary(r, catalogue) for r in catalogue.roles.values()],
    }


@router.get("/roles/{role_id}")
def get_role(role_id: int, db: DB, _principal: OptionalUser) -> dict[str, Any]:
    catalogue = load_catalogue(db)
    role = catalogue.roles.get(role_id)
    if role is None:
        raise NotFound("Role not found.")
    return _role_summary(role, catalogue)


@router.get("/catalogue/skills")
def list_catalogue_skills(db: DB, _principal: OptionalUser) -> dict[str, Any]:
    catalogue = load_catalogue(db)
    return {
        "skills": [
            {
                "id": s.id,
                "slug": s.slug,
                "name": s.name,
                "category": s.category,
                "kind": s.kind,
                "description": s.description,
                "prerequisites": [{"skill_id": p, "min_level": lvl} for p, lvl in catalogue.prerequisites.get(s.id, [])],
            }
            for s in sorted(catalogue.skills.values(), key=lambda s: (s.category, s.name))
        ]
    }


# ----------------------------------------------------------------------------- readiness


@router.get("/readiness/model")
def readiness_model_info(db: DB, _principal: OptionalUser) -> dict[str, Any]:
    """Model card essentials for the active model (or an explicit 'unavailable')."""
    m = registry.active()
    if m is None:
        return {"available": False, **registry.status(), "target_definition": TARGET_DEFINITION}
    mf = m.manifest
    return {
        "available": True,
        "version": m.version,
        "algorithm": mf["algorithm"],
        "is_synthetic": m.is_synthetic,
        "target_definition": TARGET_DEFINITION,
        "dataset": {
            "source": mf["dataset"]["source"],
            "splits": mf["dataset"]["splits"],
            "origin": mf["dataset"]["provenance"].get("origin"),
        },
        "test_metrics": {
            k: mf["metrics"]["test_calibrated"][k]
            for k in ("roc_auc", "pr_auc", "brier", "ece", "f1", "precision", "recall", "accuracy")
        },
        "test_ci95": mf["metrics"]["test_ci95"],
        "confusion_matrix": mf["metrics"]["test_calibrated"]["confusion_matrix"],
        "calibration": dict(mf["calibration"]),
        "bands": mf["thresholds"]["bands"],
        "band_observed_rates": mf["metrics"]["test_bands"],
        "model_selection": {
            "rule": mf["model_selection"]["rule"],
            "baseline": mf["model_selection"]["baseline"],
            "candidates": {k: v["cv"] for k, v in mf["model_selection"]["candidates"].items()},
        },
        "global_importance": mf["global_importance"],
        "permutation_importance": mf["permutation_importance_test"],
        "fairness": mf.get("fairness"),
        "fairness_note": mf.get("fairness_note"),
        "leakage_checks": {k: v for k, v in mf["leakage_checks"].items() if k != "feature_label_correlations"},
        "limitations": mf["limitations"],
        "features": [{"name": f.name, "label": f.label, "description": f.description, "unit": f.unit} for f in FEATURES],
        "trained_at": mf["created_at"],
    }


@router.post("/readiness/analyse")
def run_readiness(principal: CurrentUser, db: DB) -> dict[str, Any]:
    limiter.hit(EXPENSIVE_USER, str(principal.id))
    snap = ensure_snapshot(db, principal.id, "readiness_requested")
    result = predict(snap.features)
    if not result.get("available"):
        db.commit()
        return {
            "available": False,
            "reason": result.get("reason_unavailable"),
            "message": "The readiness model is not available. No estimate has been produced.",
        }
    pred = store_prediction(db, principal.id, snap, result)
    db.commit()
    return {**_strip(result), "prediction_id": pred.id, "snapshot_version": snap.version, "created_at": pred.created_at}


def _strip(result: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in result.items() if k not in ("model_db_id", "raw_score")}


@router.get("/readiness/latest")
def latest_readiness(principal: CurrentUser, db: DB) -> dict[str, Any]:
    pred = db.scalar(select(Prediction).where(Prediction.user_id == principal.id).order_by(Prediction.created_at.desc()).limit(1))
    model_status = registry.status()
    if pred is None:
        return {"exists": False, "model": model_status}
    mv = db.get(ModelVersion, pred.model_version_id)
    snap = db.get(TwinSnapshot, pred.snapshot_id) if pred.snapshot_id else None
    current = latest_snapshot(db, principal.id)
    return {
        "exists": True,
        "prediction_id": pred.id,
        "created_at": pred.created_at,
        "band": pred.band,
        "probability": pred.probability,
        "explanation": pred.explanation,
        "warnings": pred.warnings,
        "model_version": mv.version if mv else None,
        "is_synthetic_model": mv.is_synthetic if mv else None,
        "snapshot_version": snap.version if snap else None,
        "stale": bool(current and snap and current.version != snap.version)
        or (mv is not None and model_status.get("version") not in (None, mv.version)),
        "model": model_status,
    }


@router.get("/readiness/history")
def readiness_history(principal: CurrentUser, db: DB, limit: int = Query(default=50, ge=1, le=200)) -> dict[str, Any]:
    preds = prediction_history(db, principal.id, limit)
    versions = {mv.id: mv.version for mv in db.scalars(select(ModelVersion))}
    return {
        "items": [
            {
                "id": p.id,
                "created_at": p.created_at,
                "band": p.band,
                "probability": p.probability,
                "model_version": versions.get(p.model_version_id),
            }
            for p in preds
        ]
    }


# ----------------------------------------------------------------------------- gaps & matching


def _config(optional_weight: float, unlock_bonus: float, blocking_bonus: float, unknown_gap_assumption: float) -> GapConfig:
    return GapConfig(
        optional_weight=optional_weight,
        unlock_bonus=unlock_bonus,
        blocking_bonus=blocking_bonus,
        unknown_gap_assumption=unknown_gap_assumption,
    )


@router.get("/skill-gaps/roles/{role_id}")
def role_gap_analysis(
    role_id: int,
    principal: CurrentUser,
    db: DB,
    optional_weight: float = Query(default=0.5, ge=0, le=1),
    unlock_bonus: float = Query(default=0.15, ge=0, le=1),
    blocking_bonus: float = Query(default=0.2, ge=0, le=1),
    unknown_gap_assumption: float = Query(default=0.5, ge=0, le=1),
) -> dict[str, Any]:
    state, catalogue, estimates = estimates_for(db, principal.id)
    role = catalogue.roles.get(role_id)
    if role is None:
        raise NotFound("Role not found.")
    preferred = [catalogue.roles[r] for r in state.profile.get("preferred_role_ids", []) if r in catalogue.roles]
    cfg = _config(optional_weight, unlock_bonus, blocking_bonus, unknown_gap_assumption)
    result = analyse_role(role, estimates, catalogue, config=cfg, other_roles=preferred)
    for g in result.gaps:
        res_ids = catalogue.resources_by_skill.get(g.skill_id, [])
        g_dict_resources = [catalogue.resources[r] for r in res_ids]
        g.__dict__["resources"] = [
            {
                "id": r.id,
                "title": r.title,
                "provider": r.provider,
                "url": r.url,
                "verification_status": r.verification_status,
                "est_hours": [r.est_hours_min, r.est_hours_max],
                "level": [r.level_min, r.level_max],
                "cost": r.cost,
            }
            for r in sorted(g_dict_resources, key=lambda r: (r.verification_status != "verified", r.level_min))
        ][:3]
    return {
        "config": cfg.__dict__,
        "formula_doc": "docs/methodology/skill-gap.md",
        **result.to_dict(),
        "gaps": [g.__dict__ for g in result.gaps],
        "disclaimer": "A profile-to-framework match, not a probability of being hired.",
    }


@router.get("/skill-gaps/summary")
def role_matches(principal: CurrentUser, db: DB) -> dict[str, Any]:
    state, catalogue, estimates = estimates_for(db, principal.id)
    matches = analyse_all_roles(
        list(catalogue.roles.values()), estimates, catalogue, preferred_role_ids=state.profile.get("preferred_role_ids", [])
    )
    target = state.profile.get("target_role_id")
    return {
        "target_role_id": target,
        "matches": [
            {
                **m.to_dict(include_gaps=False),
                "top_gaps": [
                    {"skill": g.skill_name, "action": g.action, "gap": g.gap, "priority": g.priority}
                    for g in m.gaps
                    if g.action != "maintain"
                ][:3],
            }
            for m in matches
        ],
        "disclaimer": "Match scores compare your profile with the role framework. They are not hiring probabilities.",
    }


@router.get("/skill-gaps/sensitivity")
def role_ranking_sensitivity(
    principal: CurrentUser,
    db: DB,
    perturbation: float = Query(default=0.2, ge=0.05, le=0.5),
    samples: int = Query(default=200, ge=50, le=500),
) -> dict[str, Any]:
    limiter.hit(EXPENSIVE_USER, str(principal.id))
    _, catalogue, estimates = estimates_for(db, principal.id)
    return ranking_sensitivity(list(catalogue.roles.values()), estimates, catalogue, samples=samples, perturbation=perturbation)


# ----------------------------------------------------------------------------- simulations


@router.post("/simulations/run")
def run_simulation(body: SimulationRequest, principal: CurrentUser, db: DB) -> dict[str, Any]:
    limiter.hit(SIMULATION_USER, str(principal.id))
    return simulate(db, principal.id, body)


class SaveScenarioIn(StrictModel):
    name: str = Field(min_length=1, max_length=80)
    request: SimulationRequest


@router.post("/simulations/scenarios", status_code=status.HTTP_201_CREATED)
def save_scenario(body: SaveScenarioIn, principal: CurrentUser, db: DB) -> dict[str, Any]:
    limiter.hit(SIMULATION_USER, str(principal.id))
    count = len(db.scalars(select(WhatIfScenario.id).where(WhatIfScenario.user_id == principal.id)).all())
    if count >= 50:
        raise AppError("Scenario limit reached (50). Delete old scenarios first.", code="limit_reached", status_code=422)
    result = simulate(db, principal.id, body.request)
    snap = ensure_snapshot(db, principal.id, "scenario_saved")
    m = registry.active()
    sc = WhatIfScenario(
        user_id=principal.id,
        name=body.name,
        base_snapshot_id=snap.id,
        model_version_id=m.db_id if m else None,
        changes=body.request.model_dump(),
        result=result,
    )
    db.add(sc)
    audit.record(db, "simulation.saved", actor_id=principal.id, target_type="scenario")
    db.commit()
    return {"id": sc.id, "name": sc.name, "created_at": sc.created_at, "result": result}


@router.get("/simulations/scenarios")
def list_scenarios(principal: CurrentUser, db: DB) -> dict[str, Any]:
    rows = db.scalars(
        select(WhatIfScenario).where(WhatIfScenario.user_id == principal.id).order_by(WhatIfScenario.created_at.desc())
    ).all()
    return {
        "items": [
            {"id": s.id, "name": s.name, "created_at": s.created_at, "changes": s.changes, "result": s.result} for s in rows
        ]
    }


@router.delete("/simulations/scenarios/{scenario_id}", response_model=Message)
def delete_scenario(scenario_id: uuid.UUID, principal: CurrentUser, db: DB) -> Message:
    sc = db.scalar(select(WhatIfScenario).where(WhatIfScenario.id == scenario_id, WhatIfScenario.user_id == principal.id))
    if sc is None:
        raise NotFound("Scenario not found.")
    db.delete(sc)
    db.commit()
    return Message(message="Scenario deleted.")


@router.get("/twin/features")
def current_features(principal: CurrentUser, db: DB) -> dict[str, Any]:
    state, catalogue, estimates = estimates_for(db, principal.id)
    feats = build_features(state, catalogue, estimates)
    return {
        "features": [
            {
                "name": f.name,
                "label": f.label,
                "value": feats[f.name],
                "unit": f.unit,
                "min": f.minimum,
                "max": f.maximum,
                "description": f.description,
            }
            for f in FEATURES
        ]
    }
