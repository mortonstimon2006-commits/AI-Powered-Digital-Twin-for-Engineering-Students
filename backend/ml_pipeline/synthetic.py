"""Synthetic DEVELOPMENT cohort for the readiness model.

!! This data is simulated. It exists so the pipeline (validation, splitting, tuning,
!! calibration, explanation, fairness reporting, inference) can be built and tested end to end
!! before real, consented, assessor-labelled data exists. Metrics measured on it describe how
!! well a model recovers THIS generative process — they say nothing about real students.

Generative process (all parameters below are design choices, documented in
docs/ml/dataset-card.md):

  per student:   aptitude a ~ N(0,1), diligence d ~ N(0,1), communication k ~ N(0,1),
                 focus ∈ {software, data, ml, web}, specialization ∈ {CSE, IT, ECE, AI-DS}
  per snapshot:  semester s ∈ {5..8} (1–3 snapshots per student, increasing),
                 progress p = (s − 5) / 3
                 latent competency c = 0.6a + 0.5d + 0.6p + N(0, 0.3²)
  observed features are noisy, partially missing proxies of (a, d, k, c, focus); self-rated
  category levels are inflated when evidence strength is low.
  label (assessor judgement): z = 1.4c + 0.5k + 0.3·[deployed project] + N(0, 0.6²);
                 ready = z > q(0.65) of z  (≈35 % positives), then 5 % of labels flipped
                 (assessor inconsistency).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.ml.feature_schema import CATEGORY_FEATURES, FEATURE_NAMES

GENERATOR_VERSION = "synthetic-cohort-v1"

FOCUS_CATEGORIES = {
    "software": {"programming", "dsa", "databases"},
    "data": {"data", "databases", "programming"},
    "ml": {"ml_ai", "data", "programming"},
    "web": {"web", "programming", "databases", "cloud_devops"},
}


def _sigmoid(x: np.ndarray | float) -> np.ndarray | float:
    return 1.0 / (1.0 + np.exp(-x))


def generate_cohort(n_students: int = 1500, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows: list[dict[str, object]] = []
    focuses = list(FOCUS_CATEGORIES)
    for sid in range(n_students):
        a, d, k = rng.normal(size=3)
        focus = focuses[rng.integers(len(focuses))]
        spec = rng.choice(["CSE", "IT", "ECE", "AI-DS"], p=[0.4, 0.25, 0.15, 0.2])
        base_cgpa = float(np.clip(7.0 + 0.8 * a + 0.4 * d + rng.normal(0, 0.6), 4.0, 10.0))
        inflation = rng.uniform(0.0, 0.8)
        n_snap = int(rng.integers(1, 4))
        semesters = sorted(rng.choice([5, 6, 7, 8], size=n_snap, replace=False).tolist())
        for sem in semesters:
            p = (sem - 5) / 3
            c = 0.6 * a + 0.5 * d + 0.6 * p + rng.normal(0, 0.3)
            ev_strength = float(_sigmoid(0.8 * d + 0.5 * p + rng.normal(0, 0.7)))
            row: dict[str, object] = {"student_id": f"S{sid:05d}", "semester": float(sem), "specialization": spec, "focus": focus}
            row["cgpa"] = round(float(np.clip(base_cgpa + rng.normal(0, 0.15), 0, 10)), 2) if rng.random() > 0.05 else None
            any_known = False
            for cat in CATEGORY_FEATURES:
                related = cat in FOCUS_CATEGORIES[focus]
                if rng.random() < (0.15 if related else 0.45):
                    row[f"lvl_{cat}"] = None
                    continue
                true_lvl = 1.2 + 0.7 * c + (0.6 if related else -0.3) + rng.normal(0, 0.5)
                observed = true_lvl + inflation * (1 - ev_strength) * 1.5
                row[f"lvl_{cat}"] = round(float(np.clip(observed, 0, 4)), 2)
                any_known = True
            row["evidence_strength"] = round(ev_strength, 3) if any_known else None
            projects = int(np.clip(rng.poisson(np.exp(0.6 + 0.4 * d + 0.5 * p)), 0, 15))
            deployed = int(rng.binomial(projects, float(_sigmoid(-0.5 + 0.6 * c)))) if projects else 0
            row["projects"] = float(projects)
            row["deployed_projects"] = float(deployed)
            has_intern = rng.random() < float(_sigmoid(-1.2 + 0.7 * c + 0.8 * p))
            row["internship_months"] = round(float(rng.uniform(1, 6) * (1 + p)), 1) if has_intern else 0.0
            row["certifications_verified"] = float(rng.poisson(0.3 + 0.4 * max(d, 0)))
            row["hackathons"] = float(rng.poisson(0.4 + 0.5 * max((a + d) / 2, 0)))
            row["coding_assessment_pct"] = (
                round(float(np.clip(55 + 15 * c + rng.normal(0, 10), 0, 100)), 1) if rng.random() < 0.65 else None
            )
            row["communication_pct"] = (
                round(float(np.clip(60 + 8 * k + 5 * c + rng.normal(0, 10), 0, 100)), 1) if rng.random() < 0.5 else None
            )
            row["mock_interview_pct"] = (
                round(float(np.clip(50 + 12 * c + 6 * k + rng.normal(0, 12), 0, 100)), 1)
                if rng.random() < 0.25 + 0.3 * p
                else None
            )
            row["_z"] = 1.4 * c + 0.5 * k + 0.3 * (deployed > 0) + rng.normal(0, 0.6)
            rows.append(row)

    df = pd.DataFrame(rows)
    threshold = float(np.quantile(df["_z"], 0.65))
    label = (df["_z"] > threshold).astype(int).to_numpy().copy()
    flip = rng.random(len(df)) < 0.05
    label[flip] = 1 - label[flip]
    df["label"] = label
    df = df.drop(columns=["_z"])
    ordered = ["student_id", "specialization", "focus", *FEATURE_NAMES, "label"]
    return df[ordered]
