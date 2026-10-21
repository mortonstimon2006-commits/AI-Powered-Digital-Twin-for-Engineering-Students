"""Registering trained artifacts in `model_versions`.

Used by the training pipeline (`ml_pipeline.train --register/--activate`) and by
`python -m app.cli deploy-init`, which registers artifacts shipped inside the API image so a
fresh database (for example a managed free-tier Postgres) gets a working, verified model.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select, update

from app.config import get_settings
from app.db import system_session
from app.ml.feature_schema import schema_hash
from app.ml.registry import sha256_file
from app.models import ModelVersion


def register_artifact(artifact_dir: Path, activate: bool) -> int:
    """Adds the artifact to `model_versions` (idempotent by version) and optionally activates it."""
    manifest = json.loads((artifact_dir / "manifest.json").read_text(encoding="utf-8"))
    base = get_settings().model_artifact_dir.resolve()
    rel = (artifact_dir / "model.joblib").resolve().relative_to(base).as_posix()
    sha = sha256_file(artifact_dir / "model.joblib")
    if sha != manifest["model_file_sha256"]:
        raise ValueError(f"artifact checksum does not match manifest: {artifact_dir.name}")
    with system_session() as db:
        existing = db.scalar(select(ModelVersion).where(ModelVersion.version == manifest["version"]))
        if existing:
            mv = existing
        else:
            mv = ModelVersion(
                version=manifest["version"],
                kind=manifest["kind"],
                algorithm=manifest["algorithm"],
                target=manifest["target"]["name"],
                status="candidate",
                is_synthetic=manifest["dataset"]["is_synthetic"],
                dataset_ref={k: manifest["dataset"][k] for k in ("source", "sha256", "splits", "is_synthetic")},
                metrics={
                    "test": manifest["metrics"]["test_calibrated"],
                    "ci95": manifest["metrics"]["test_ci95"],
                    "calibration": {k: v for k, v in manifest["calibration"].items() if k != "reliability_test"},
                },
                feature_schema={"hash": manifest["feature_schema_hash"], "features": [f["name"] for f in manifest["features"]]},
                artifact_path=rel,
                artifact_sha256=sha,
                trained_at=datetime.fromisoformat(manifest["created_at"]),
                notes="; ".join(manifest["limitations"][:2]),
            )
            db.add(mv)
            db.flush()
        if activate:
            db.execute(
                update(ModelVersion)
                .where(ModelVersion.kind == mv.kind, ModelVersion.status == "active", ModelVersion.id != mv.id)
                .values(status="retired")
            )
            db.flush()
            mv.status = "active"
            mv.activated_at = datetime.now(UTC)
        return mv.id


def register_bundled() -> dict[str, list[str]]:
    """Registers every valid artifact found in MODEL_ARTIFACT_DIR. For each model kind with no
    active model, activates the most recently trained artifact. Never replaces a model an admin
    activated, so restarting a deployment cannot silently switch models. Artifacts whose file
    checksum or feature schema does not match are skipped and reported, not registered."""
    base = get_settings().model_artifact_dir.resolve()
    found: list[tuple[str, str, Path]] = []
    rejected: list[str] = []
    candidates = sorted(p for p in base.iterdir() if p.is_dir()) if base.is_dir() else []
    for d in candidates:
        if not ((d / "manifest.json").is_file() and (d / "model.joblib").is_file()):
            continue
        manifest = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
        if manifest.get("feature_schema_hash") != schema_hash() or sha256_file(d / "model.joblib") != manifest.get(
            "model_file_sha256"
        ):
            rejected.append(d.name)
            continue
        found.append((manifest["kind"], manifest["created_at"], d))
    registered: list[str] = []
    for _, _, d in found:
        register_artifact(d, activate=False)
        registered.append(d.name)
    activated: list[str] = []
    for kind in sorted({k for k, _, _ in found}):
        with system_session() as db:
            has_active = db.scalar(select(ModelVersion.id).where(ModelVersion.kind == kind, ModelVersion.status == "active"))
        if has_active is None:
            _, _, newest = max((f for f in found if f[0] == kind), key=lambda f: f[1])
            register_artifact(newest, activate=True)
            activated.append(newest.name)
    return {"registered": registered, "activated": activated, "rejected": rejected}
