"""Versioned model registry.

Artifacts live on disk under MODEL_ARTIFACT_DIR/<version>/ (model.joblib + manifest.json);
their metadata, metrics and SHA-256 live in `model_versions`. Loading verifies:
  * the artifact path stays inside the artifact directory (no traversal),
  * the file checksum matches the registered checksum (joblib = pickle: never load an
    unverified file),
  * the feature-schema hash matches the running code,
  * the scikit-learn / XGBoost major.minor versions match the training environment.
If any check fails the model is reported UNAVAILABLE — the API never substitutes another model.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import joblib
from sqlalchemy import select

from app.config import get_settings
from app.ml.feature_schema import schema_hash

log = logging.getLogger("twinpath.ml")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _major_minor(v: str) -> str:
    return ".".join(v.split(".")[:2])


@dataclass
class LoadedModel:
    db_id: int
    version: str
    manifest: dict[str, Any]
    pipeline: Any  # imputer + estimator (uncalibrated; used for SHAP)
    calibrated: Any | None  # calibrated wrapper (used for probabilities) or None
    background: Any  # transformed background sample for SHAP
    feature_names_out: list[str]
    _explainer: Any = field(default=None, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @property
    def calibration_validated(self) -> bool:
        return bool(self.manifest.get("calibration", {}).get("validated"))

    @property
    def is_synthetic(self) -> bool:
        return bool(self.manifest.get("dataset", {}).get("is_synthetic"))


class ModelRegistry:
    def __init__(self) -> None:
        self._active: LoadedModel | None = None
        self._error: str | None = None
        self._lock = threading.Lock()

    # -- loading -------------------------------------------------------------
    def load_artifact(self, artifact_path: str, expected_sha256: str, db_id: int, version: str) -> LoadedModel:
        base = get_settings().model_artifact_dir.resolve()
        model_file = (base / artifact_path).resolve()
        if base not in model_file.parents:
            raise ValueError("artifact path escapes the artifact directory")
        if not model_file.is_file():
            raise FileNotFoundError(f"artifact not found for model {version}")
        actual = sha256_file(model_file)
        if actual != expected_sha256:
            raise ValueError(f"checksum mismatch for model {version}")
        manifest = json.loads((model_file.parent / "manifest.json").read_text(encoding="utf-8"))
        if manifest.get("feature_schema_hash") != schema_hash():
            raise ValueError("feature schema of the artifact does not match this code version")
        import sklearn
        import xgboost

        libs = manifest.get("libraries", {})
        for name, installed in (("scikit-learn", sklearn.__version__), ("xgboost", xgboost.__version__)):
            trained = libs.get(name)
            if trained and _major_minor(trained) != _major_minor(installed):
                raise ValueError(f"{name} {installed} differs from training version {trained}; retrain or pin")
        bundle = joblib.load(model_file)
        return LoadedModel(
            db_id=db_id,
            version=version,
            manifest=manifest,
            pipeline=bundle["pipeline"],
            calibrated=bundle.get("calibrated"),
            background=bundle["background"],
            feature_names_out=list(bundle["feature_names_out"]),
        )

    def warm(self) -> None:
        from app.db import system_session
        from app.models import ModelVersion

        with self._lock:
            try:
                with system_session() as db:
                    mv = db.scalar(
                        select(ModelVersion).where(ModelVersion.kind == "readiness_classifier", ModelVersion.status == "active")
                    )
                    if mv is None:
                        self._active, self._error = None, "no active readiness model is registered"
                        return
                    self._active = self.load_artifact(mv.artifact_path, mv.artifact_sha256, mv.id, mv.version)
                    self._error = None
                    log.info("model loaded", extra={"ctx": {"version": mv.version}})
            except Exception as exc:
                self._active, self._error = None, str(exc)[:300]
                log.error("readiness model unavailable", extra={"ctx": {"reason": self._error}})

    # -- access --------------------------------------------------------------
    def active(self) -> LoadedModel | None:
        return self._active

    def active_available(self) -> bool:
        return self._active is not None

    def status(self) -> dict[str, Any]:
        m = self._active
        return {
            "available": m is not None,
            "version": m.version if m else None,
            "reason_unavailable": None if m else self._error,
        }


registry = ModelRegistry()
