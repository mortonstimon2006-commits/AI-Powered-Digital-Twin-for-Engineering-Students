"""Dataset sources, schema validation and quality checks for the readiness model.

Sources:
  synthetic           clearly-labelled development cohort (ml_pipeline.synthetic)
  csv:<path>          historical/assessor-labelled CSV. Requires a sidecar <path>.provenance.json
                      describing origin, licence/permission, label definition and collection
                      period — training refuses to run without it.
  app_labels          assessor labels recorded in the app (readiness_labels) joined with the
                      frozen twin snapshot they were given against, restricted to students who
                      granted the `research_use` consent.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.ml.feature_schema import FEATURE_BY_NAME, FEATURE_NAMES, TARGET_DEFINITION, TARGET_NAME
from ml_pipeline.synthetic import GENERATOR_VERSION, generate_cohort

REQUIRED_PROVENANCE_KEYS = {"origin", "permission", "label_definition", "collection_period", "contact"}
GROUP_COL = "student_id"
LABEL_COL = "label"


@dataclass
class Dataset:
    frame: pd.DataFrame
    provenance: dict[str, Any]
    is_synthetic: bool
    quality: dict[str, Any] = field(default_factory=dict)

    @property
    def sha256(self) -> str:
        csv = self.frame.sort_values([GROUP_COL, "semester"]).to_csv(index=False).encode()
        return hashlib.sha256(csv).hexdigest()


def validate_and_clean(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Schema + quality checks. Rows violating hard constraints are REMOVED and counted;
    statistical outliers are only REPORTED (they may be genuine)."""
    report: dict[str, Any] = {"rows_in": len(df)}
    missing_cols = [c for c in (*FEATURE_NAMES, GROUP_COL, LABEL_COL) if c not in df.columns]
    if missing_cols:
        raise ValueError(f"dataset is missing required columns: {missing_cols}")
    forbidden = [
        c
        for c in df.columns
        if c.lower() in {"name", "email", "phone", "gender", "religion", "caste", "address", "dob", "date_of_birth", "aadhaar"}
    ]
    if forbidden:
        raise ValueError(f"dataset contains personal/protected columns that must not be used: {forbidden}")

    df = df.copy()
    for col in FEATURE_NAMES:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype(float)
    bad_label = ~df[LABEL_COL].isin([0, 1])
    report["invalid_label_rows"] = int(bad_label.sum())
    df = df[~bad_label]

    out_of_range = pd.Series(False, index=df.index)
    range_violations: dict[str, int] = {}
    for col in FEATURE_NAMES:
        spec = FEATURE_BY_NAME[col]
        viol = df[col].notna() & ((df[col] < spec.minimum) | (df[col] > spec.maximum))
        if viol.any():
            range_violations[col] = int(viol.sum())
        out_of_range |= viol
    report["range_violation_rows"] = int(out_of_range.sum())
    report["range_violations_by_feature"] = range_violations
    df = df[~out_of_range]

    dup = df.duplicated(subset=[GROUP_COL, *FEATURE_NAMES, LABEL_COL], keep="first")
    report["exact_duplicates_removed"] = int(dup.sum())
    df = df[~dup]
    conflict = df.groupby([GROUP_COL, "semester"])[LABEL_COL].nunique()
    report["conflicting_label_snapshots"] = int((conflict > 1).sum())

    report["missing_share"] = {c: round(float(df[c].isna().mean()), 4) for c in FEATURE_NAMES}
    outliers: dict[str, int] = {}
    for col in FEATURE_NAMES:
        s = df[col].dropna()
        if len(s) < 20:
            continue
        q1, q3 = np.percentile(s, [25, 75])
        iqr = q3 - q1
        if iqr > 0:
            n = int(((s < q1 - 3 * iqr) | (s > q3 + 3 * iqr)).sum())
            if n:
                outliers[col] = n
    report["iqr3_outliers_reported_not_removed"] = outliers
    report["rows_out"] = len(df)
    report["students"] = int(df[GROUP_COL].nunique())
    report["positive_rate"] = round(float(df[LABEL_COL].mean()), 4)
    report["snapshots_per_student"] = round(len(df) / max(df[GROUP_COL].nunique(), 1), 2)
    return df.reset_index(drop=True), report


def load_dataset(source: str, *, seed: int = 42, n_students: int = 1500) -> Dataset:
    if source == "synthetic":
        frame = generate_cohort(n_students=n_students, seed=seed)
        provenance = {
            "origin": f"Simulated by {GENERATOR_VERSION} (seed={seed}, n_students={n_students})",
            "permission": "Not applicable — no real person's data.",
            "label_definition": TARGET_DEFINITION,
            "target": TARGET_NAME,
            "collection_period": "n/a (simulated)",
            "contact": "project team",
            "warning": "SYNTHETIC DEVELOPMENT DATA. Metrics do not describe real students.",
        }
        is_synth = True
    elif source.startswith("csv:"):
        path = Path(source[4:])
        prov_path = path.with_suffix(path.suffix + ".provenance.json")
        if not prov_path.is_file():
            raise ValueError(f"refusing to train on {path.name}: provenance file {prov_path.name} is required")
        provenance = json.loads(prov_path.read_text(encoding="utf-8"))
        missing = REQUIRED_PROVENANCE_KEYS - set(provenance)
        if missing:
            raise ValueError(f"provenance file is missing keys: {sorted(missing)}")
        frame = pd.read_csv(path)
        is_synth = bool(provenance.get("is_synthetic", False))
    elif source == "app_labels":
        frame, provenance = _load_app_labels()
        is_synth = False
    else:
        raise ValueError(f"unknown dataset source: {source}")
    clean, quality = validate_and_clean(frame)
    return Dataset(frame=clean, provenance=provenance, is_synthetic=is_synth, quality=quality)


def _load_app_labels() -> tuple[pd.DataFrame, dict[str, Any]]:
    from sqlalchemy import select

    from app.db import system_session
    from app.models import Consent, ReadinessLabel, StudentProfile, TwinSnapshot

    rows = []
    with system_session() as db:
        q = (
            select(ReadinessLabel, TwinSnapshot, StudentProfile.specialization)
            .join(TwinSnapshot, TwinSnapshot.id == ReadinessLabel.snapshot_id)
            .join(Consent, (Consent.user_id == ReadinessLabel.user_id) & (Consent.purpose == "research_use"))
            .outerjoin(StudentProfile, StudentProfile.user_id == ReadinessLabel.user_id)
            .where(Consent.granted.is_(True))
        )
        for label, snap, spec in db.execute(q):
            feats = snap.features
            rows.append(
                {
                    "student_id": str(label.user_id),
                    "specialization": spec or "unknown",
                    **{k: feats.get(k) for k in FEATURE_NAMES},
                    "label": 1 if label.label == "ready" else 0,
                }
            )
    provenance = {
        "origin": "AI Career Guidance App in-app assessor labels (readiness_labels) with frozen twin snapshots",
        "permission": "Students who granted the research_use consent at labelling/export time",
        "label_definition": TARGET_DEFINITION,
        "target": TARGET_NAME,
        "collection_period": "see rated_at range in the report",
        "contact": "app administrators",
    }
    return pd.DataFrame(rows), provenance
