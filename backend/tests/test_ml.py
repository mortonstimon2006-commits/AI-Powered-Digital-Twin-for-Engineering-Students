from __future__ import annotations

import json
import shutil

import numpy as np
import pandas as pd
import pytest

from app.ml.feature_schema import FEATURE_NAMES, schema_hash, validate_vector
from ml_pipeline.datasets import load_dataset, validate_and_clean
from ml_pipeline.evaluation import expected_calibration_error, grouped_bootstrap_ci
from ml_pipeline.synthetic import generate_cohort
from ml_pipeline.train import grouped_split


def test_feature_vector_validation():
    good = dict.fromkeys(FEATURE_NAMES)
    good.update(cgpa=8.0, semester=6.0, projects=2.0)
    assert validate_vector(good) == []
    assert validate_vector({**good, "cgpa": 11.0})
    assert validate_vector({**good, "projects": 2.5})  # integer feature
    assert validate_vector({**good, "unknown_feature": 1.0})  # unknown key
    assert validate_vector({**good, "cgpa": float("nan")})  # NaN must be None, not a number


def test_synthetic_generator_is_deterministic():
    a = generate_cohort(n_students=50, seed=3)
    b = generate_cohort(n_students=50, seed=3)
    c = generate_cohort(n_students=50, seed=4)
    pd.testing.assert_frame_equal(a, b)
    assert not a.equals(c)
    assert set(a.columns) >= {*FEATURE_NAMES, "student_id", "label"}


def test_dataset_validation_removes_bad_rows_and_reports():
    base = generate_cohort(n_students=80, seed=1)
    bad_label = base.iloc[[6]].copy()
    bad_label["label"] = 7  # invalid label -> removed
    df = pd.concat([base, base.iloc[[5]], bad_label], ignore_index=True)  # + one exact duplicate
    df.loc[0, "cgpa"] = 14.0  # out of range -> removed
    clean, report = validate_and_clean(df)
    assert report["range_violation_rows"] == 1
    assert report["exact_duplicates_removed"] == 1
    assert report["invalid_label_rows"] == 1
    assert len(clean) == len(base) - 1 and clean["cgpa"].max() <= 10


def test_protected_attributes_are_refused():
    df = generate_cohort(n_students=20, seed=1)
    df["gender"] = "x"
    with pytest.raises(ValueError, match="protected"):
        validate_and_clean(df)


def test_csv_source_requires_provenance(tmp_path):
    p = tmp_path / "labels.csv"
    generate_cohort(n_students=30, seed=2).to_csv(p, index=False)
    with pytest.raises(ValueError, match="provenance"):
        load_dataset(f"csv:{p}")
    (tmp_path / "labels.csv.provenance.json").write_text(json.dumps({"origin": "x"}))
    with pytest.raises(ValueError, match="missing keys"):
        load_dataset(f"csv:{p}")


def test_grouped_split_has_no_student_leakage():
    df, _ = validate_and_clean(generate_cohort(n_students=300, seed=9))
    tr, va, te = grouped_split(df, seed=9)
    g = df["student_id"].to_numpy()
    assert not (set(g[tr]) & set(g[te])) and not (set(g[tr]) & set(g[va])) and not (set(g[va]) & set(g[te]))
    assert len(tr) + len(va) + len(te) == len(df)
    for idx in (va, te):
        assert abs(df.iloc[idx]["label"].mean() - df["label"].mean()) < 0.12  # roughly stratified


def test_ece_and_bootstrap():
    rng = np.random.default_rng(0)
    p = rng.uniform(size=2000)
    y = (rng.uniform(size=2000) < p).astype(int)  # perfectly calibrated by construction
    assert expected_calibration_error(y, p) < 0.04
    assert expected_calibration_error(y, np.clip(p + 0.3, 0, 1)) > 0.2
    ci = grouped_bootstrap_ci(y, p, np.arange(2000) // 2, 0.5, n_boot=100, seed=0)
    assert ci["roc_auc"]["low"] < ci["roc_auc"]["high"]


def test_trained_artifact_manifest_is_complete_and_honest(trained_artifact):
    m = json.loads((trained_artifact / "manifest.json").read_text(encoding="utf-8"))
    assert m["dataset"]["is_synthetic"] is True
    assert "SYNTHETIC" in m["limitations"][0]
    assert m["feature_schema_hash"] == schema_hash()
    assert m["leakage_checks"]["students_shared_between_splits"] == 0
    assert m["leakage_checks"]["shuffled_label_sanity_passed"] is True
    assert set(m["model_selection"]["candidates"]) == {"logistic_regression", "random_forest", "xgboost"}
    assert m["model_selection"]["baseline"]["cv_pr_auc_mean"] < m["metrics"]["test_calibrated"]["pr_auc"]
    for key in ("roc_auc", "pr_auc", "brier", "ece", "f1", "precision", "recall", "accuracy", "confusion_matrix"):
        assert key in m["metrics"]["test_calibrated"]
    assert (trained_artifact / "report.md").read_text(encoding="utf-8").count("SYNTHETIC DATA WARNING") == 1
    assert all((trained_artifact / f).exists() for f in m["figures"])


def test_training_is_reproducible(trained_artifact, tmp_path):
    from ml_pipeline.train import train

    again = train("synthetic", seed=7, n_students=500, out_dir=tmp_path, quick=True)
    m1 = json.loads((trained_artifact / "manifest.json").read_text(encoding="utf-8"))
    m2 = json.loads((again / "manifest.json").read_text(encoding="utf-8"))
    assert m1["dataset"]["sha256"] == m2["dataset"]["sha256"]
    assert m1["metrics"]["test_calibrated"] == m2["metrics"]["test_calibrated"]
    assert m1["model_selection"]["selected"] == m2["model_selection"]["selected"]


def test_registry_rejects_tampered_or_mismatched_artifacts(trained_artifact, tmp_path, monkeypatch):
    from app.ml.registry import ModelRegistry, sha256_file

    reg = ModelRegistry()
    model_file = trained_artifact / "model.joblib"
    rel = model_file.relative_to(trained_artifact.parent).as_posix()
    good = reg.load_artifact(rel, sha256_file(model_file), 1, "v")
    assert good.pipeline is not None
    with pytest.raises(ValueError, match="checksum"):
        reg.load_artifact(rel, "0" * 64, 1, "v")
    with pytest.raises(ValueError, match="escapes"):
        reg.load_artifact("../../etc/passwd", "0" * 64, 1, "v")
    # schema drift: a manifest built for another feature contract must be refused
    copy = trained_artifact.parent / "drifted"
    shutil.copytree(trained_artifact, copy, dirs_exist_ok=True)
    mf = json.loads((copy / "manifest.json").read_text(encoding="utf-8"))
    mf["feature_schema_hash"] = "deadbeef"
    (copy / "manifest.json").write_text(json.dumps(mf), encoding="utf-8")
    with pytest.raises(ValueError, match="schema"):
        reg.load_artifact("drifted/model.joblib", sha256_file(copy / "model.joblib"), 1, "v")


def test_deploy_init_registers_shipped_model_once(trained_artifact, tmp_path, monkeypatch):
    from sqlalchemy import select

    from app.config import get_settings
    from app.db import system_session
    from app.ml.artifacts import register_bundled
    from app.models import ModelVersion

    shutil.copytree(trained_artifact, tmp_path / trained_artifact.name)
    tampered = tmp_path / "tampered"
    shutil.copytree(trained_artifact, tampered)
    (tampered / "model.joblib").write_bytes(b"not the trained model")
    monkeypatch.setattr(get_settings(), "model_artifact_dir", tmp_path)

    first = register_bundled()
    assert first["activated"] == [trained_artifact.name]
    assert first["rejected"] == ["tampered"]
    again = register_bundled()  # every restart runs it: must be idempotent
    assert again["activated"] == [] and again["registered"] == [trained_artifact.name]
    with system_session() as db:
        rows = db.scalars(select(ModelVersion)).all()
    assert len(rows) == 1 and rows[0].status == "active"


def test_engine_without_pool_holds_no_idle_connections(monkeypatch):
    from sqlalchemy import text
    from sqlalchemy.pool import NullPool

    from app.config import get_settings
    from app.db import get_engine

    monkeypatch.setattr(get_settings(), "db_disable_pool", True)
    engine = get_engine.__wrapped__()
    try:
        assert isinstance(engine.pool, NullPool)
        with engine.connect() as conn:
            assert conn.execute(text("SELECT 1")).scalar() == 1
        assert engine.pool.status() == "NullPool"
    finally:
        engine.dispose()


def test_prediction_consistency_and_ood_warning(readiness_model):
    from app.services.career.readiness import predict

    feats = dict.fromkeys(FEATURE_NAMES)
    feats.update(cgpa=7.5, semester=6.0, lvl_programming=2.5, projects=2.0, coding_assessment_pct=60.0)
    r1, r2 = predict(feats), predict(feats)
    assert r1["calibrated_score"] == r2["calibrated_score"] and r1["band"] == r2["band"]
    sparse = predict(dict.fromkeys(FEATURE_NAMES))
    assert any(w["code"] == "low_information" for w in sparse["warnings"])
    extreme = predict({**feats, "projects": 40.0, "internship_months": 60.0})
    assert any(w["code"] == "out_of_distribution" for w in extreme["warnings"])
    # more evidence of competence should not lower the estimate for a monotone-ish profile (sanity, not a guarantee)
    better = predict({**feats, "coding_assessment_pct": 95.0, "mock_interview_pct": 90.0})
    assert better["calibrated_score"] >= r1["calibrated_score"] - 0.05
