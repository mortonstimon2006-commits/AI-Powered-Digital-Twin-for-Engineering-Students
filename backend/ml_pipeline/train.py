"""Train, evaluate, explain and package the readiness model.

    uv run python -m ml_pipeline.train --source synthetic --seed 42 [--register] [--activate]

Protocol (pre-specified; see docs/ml/model-card.md):
  1. Validate data; split by STUDENT (grouped, stratified) into train 72% / validation 14% /
     test 14% — snapshots of one student never cross splits.
  2. Tune each candidate with 5-fold StratifiedGroupKFold CV on TRAIN only (preprocessing is
     inside the pipeline, so imputation is fitted per fold). Primary metric: PR-AUC.
  3. Select the best mean CV PR-AUC; a simpler model within one standard error wins (Occam).
  4. Refit on TRAIN; fit Platt (sigmoid) calibration on VALIDATION; choose the F1 decision
     threshold on VALIDATION.
  5. Evaluate ONCE on TEST: discrimination, calibration, 95% student-clustered bootstrap CIs,
     reliability, bands, temporal slices, subgroup gaps, SHAP and permutation importance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.frozen import FrozenEstimator
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, precision_recall_curve, roc_auc_score
from sklearn.model_selection import GridSearchCV, StratifiedGroupKFold, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from app.ml.explain import global_importance, make_explainer
from app.ml.feature_schema import FEATURE_BY_NAME, FEATURE_NAMES, FEATURES, TARGET_DEFINITION, TARGET_NAME, schema_hash
from ml_pipeline.datasets import GROUP_COL, LABEL_COL, Dataset, load_dataset
from ml_pipeline.evaluation import (
    BANDS,
    band_analysis,
    grouped_bootstrap_ci,
    point_metrics,
    ranking_metrics,
    reliability_table,
    subgroup_report,
)

BACKEND = Path(__file__).resolve().parents[1]
SIMPLICITY = {"logistic_regression": 0, "random_forest": 1, "xgboost": 2}
ECE_TOLERANCE = 0.05
# Sequential by default: deterministic and avoids process-pool issues on Windows.
N_JOBS = 1


def candidates(seed: int) -> dict[str, tuple[Pipeline, dict[str, list[Any]]]]:
    imputer = lambda: SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True)  # noqa: E731
    return {
        "logistic_regression": (
            Pipeline(
                [
                    ("impute", imputer()),
                    ("scale", StandardScaler()),
                    ("model", LogisticRegression(max_iter=2000, random_state=seed)),
                ]
            ),
            {"model__C": [0.01, 0.1, 1.0, 10.0], "model__class_weight": [None, "balanced"]},
        ),
        "random_forest": (
            Pipeline([("impute", imputer()), ("model", RandomForestClassifier(n_estimators=300, random_state=seed, n_jobs=1))]),
            {"model__max_depth": [4, 8, None], "model__min_samples_leaf": [1, 5, 20]},
        ),
        "xgboost": (
            Pipeline(
                [
                    ("impute", imputer()),
                    (
                        "model",
                        XGBClassifier(
                            n_estimators=300,
                            subsample=0.8,
                            colsample_bytree=0.8,
                            eval_metric="logloss",
                            random_state=seed,
                            n_jobs=1,
                            tree_method="hist",
                        ),
                    ),
                ]
            ),
            {"model__max_depth": [2, 3, 4], "model__learning_rate": [0.03, 0.1], "model__min_child_weight": [1, 5]},
        ),
    }


def grouped_split(df: pd.DataFrame, seed: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    y, g = df[LABEL_COL].to_numpy(), df[GROUP_COL].to_numpy()
    outer = StratifiedGroupKFold(n_splits=7, shuffle=True, random_state=seed)
    rest_idx, test_idx = next(outer.split(df, y, g))
    inner = StratifiedGroupKFold(n_splits=6, shuffle=True, random_state=seed + 1)
    tr_rel, val_rel = next(inner.split(df.iloc[rest_idx], y[rest_idx], g[rest_idx]))
    train_idx, val_idx = rest_idx[tr_rel], rest_idx[val_rel]
    sets = [set(g[i]) for i in (train_idx, val_idx, test_idx)]
    assert not (sets[0] & sets[1]) and not (sets[0] & sets[2]) and not (sets[1] & sets[2]), "student leakage"
    return train_idx, val_idx, test_idx


def _split_summary(df: pd.DataFrame, idx: np.ndarray) -> dict[str, Any]:
    part = df.iloc[idx]
    return {
        "rows": len(part),
        "students": int(part[GROUP_COL].nunique()),
        "positive_rate": round(float(part[LABEL_COL].mean()), 4),
    }


def leakage_checks(df: pd.DataFrame, X_tr: pd.DataFrame, y_tr: np.ndarray, g_tr: np.ndarray, seed: int) -> dict[str, Any]:
    y_series = pd.Series(y_tr, dtype=float)
    corr = {
        c: round(float(abs(X_tr[c].reset_index(drop=True).corr(y_series))), 4)
        for c in FEATURE_NAMES
        if X_tr[c].notna().sum() > 10
    }
    rng = np.random.default_rng(seed)
    shuffled = rng.permutation(y_tr)
    pipe = Pipeline(
        [
            ("impute", SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True)),
            ("scale", StandardScaler()),
            ("model", LogisticRegression(max_iter=2000)),
        ]
    )
    auc = cross_val_score(
        pipe, X_tr, shuffled, groups=g_tr, scoring="roc_auc", cv=StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed)
    ).mean()
    id_like = [c for c in FEATURE_NAMES if "id" in c.split("_")]
    return {
        "features_used": list(FEATURE_NAMES),
        "identifier_like_features": id_like,
        "max_abs_feature_label_correlation": max(corr.values()) if corr else None,
        "feature_label_correlations": corr,
        "shuffled_label_cv_roc_auc": round(float(auc), 4),
        "shuffled_label_sanity_passed": bool(abs(auc - 0.5) < 0.06),
        "preprocessing_fitted_within_cv_folds": True,
        "students_shared_between_splits": 0,
        "temporal_note": "Each label is paired with features from the same snapshot; no later information is used.",
    }


def select_model(results: dict[str, dict[str, Any]]) -> tuple[str, str]:
    best = max(results, key=lambda k: results[k]["cv"]["pr_auc_mean"])
    best_mean = results[best]["cv"]["pr_auc_mean"]
    best_se = results[best]["cv"]["pr_auc_std"] / np.sqrt(5)
    within = [k for k in results if results[k]["cv"]["pr_auc_mean"] >= best_mean - best_se]
    chosen = min(within, key=lambda k: SIMPLICITY[k])
    rule = (
        f"Highest mean CV PR-AUC was {best} ({best_mean:.4f} ± SE {best_se:.4f}). "
        f"Candidates within one standard error: {sorted(within)}; the simplest ({chosen}) was selected."
    )
    return chosen, rule


def tune(
    name: str, pipe: Pipeline, grid: dict[str, list[Any]], X: pd.DataFrame, y: np.ndarray, g: np.ndarray, seed: int
) -> dict[str, Any]:
    cv = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed)
    scoring = {
        "pr_auc": "average_precision",
        "roc_auc": "roc_auc",
        "neg_log_loss": "neg_log_loss",
        "neg_brier": "neg_brier_score",
    }
    gs = GridSearchCV(pipe, grid, cv=cv, scoring=scoring, refit=False, n_jobs=N_JOBS)
    t0 = time.perf_counter()
    gs.fit(X, y, groups=g)
    res = gs.cv_results_
    i = int(np.argmax(res["mean_test_pr_auc"]))
    return {
        "params": {k.replace("model__", ""): v for k, v in res["params"][i].items()},
        "raw_params": res["params"][i],
        "grid_size": len(res["params"]),
        "seconds": round(time.perf_counter() - t0, 1),
        "cv": {
            "pr_auc_mean": float(res["mean_test_pr_auc"][i]),
            "pr_auc_std": float(res["std_test_pr_auc"][i]),
            "roc_auc_mean": float(res["mean_test_roc_auc"][i]),
            "roc_auc_std": float(res["std_test_roc_auc"][i]),
            "log_loss_mean": float(-res["mean_test_neg_log_loss"][i]),
            "brier_mean": float(-res["mean_test_neg_brier"][i]),
        },
    }


def f1_threshold(y: np.ndarray, p: np.ndarray) -> float:
    prec, rec, thr = precision_recall_curve(y, p)
    f1 = 2 * prec * rec / np.clip(prec + rec, 1e-12, None)
    return float(thr[int(np.argmax(f1[:-1]))])


def make_figures(
    out: Path,
    y: np.ndarray,
    p_uncal: np.ndarray,
    p_cal: np.ndarray,
    threshold: float,
    importance: list[dict[str, Any]],
    comparison: dict[str, dict[str, Any]],
    synthetic: bool,
) -> list[str]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from sklearn.calibration import CalibrationDisplay
    from sklearn.metrics import ConfusionMatrixDisplay, PrecisionRecallDisplay, RocCurveDisplay

    figs = out / "figures"
    figs.mkdir(parents=True, exist_ok=True)
    tag = " — SYNTHETIC DATA" if synthetic else ""
    made = []

    def save(fig: Any, name: str) -> None:
        fig.tight_layout()
        fig.savefig(figs / name, dpi=130)
        plt.close(fig)
        made.append(f"figures/{name}")

    fig, ax = plt.subplots(figsize=(5, 4.5))
    RocCurveDisplay.from_predictions(y, p_cal, ax=ax, name="calibrated")
    ax.plot([0, 1], [0, 1], "--", color="grey", lw=1)
    ax.set_title("ROC (test)" + tag, fontsize=10)
    save(fig, "roc.png")

    fig, ax = plt.subplots(figsize=(5, 4.5))
    PrecisionRecallDisplay.from_predictions(y, p_cal, ax=ax, name="calibrated")
    ax.axhline(y.mean(), ls="--", color="grey", lw=1, label="prevalence")
    ax.legend()
    ax.set_title("Precision–recall (test)" + tag, fontsize=10)
    save(fig, "pr.png")

    fig, ax = plt.subplots(figsize=(5, 4.5))
    CalibrationDisplay.from_predictions(y, p_uncal, n_bins=10, ax=ax, name="uncalibrated")
    CalibrationDisplay.from_predictions(y, p_cal, n_bins=10, ax=ax, name="Platt-calibrated")
    ax.set_title("Reliability diagram (test)" + tag, fontsize=10)
    save(fig, "calibration.png")

    fig, ax = plt.subplots(figsize=(4.5, 4))
    ConfusionMatrixDisplay.from_predictions(
        y, (p_cal >= threshold).astype(int), ax=ax, display_labels=["not ready", "ready"], colorbar=False
    )
    ax.set_title(f"Confusion matrix @ {threshold:.2f}" + tag, fontsize=10)
    save(fig, "confusion.png")

    top = importance[:12][::-1]
    fig, ax = plt.subplots(figsize=(6, 4.5))
    ax.barh([t["label"] for t in top], [t["mean_abs_shap"] for t in top], color="#4f8fba")
    ax.set_xlabel("mean |SHAP| (model output units)")
    ax.set_title("Global feature attribution (test)" + tag, fontsize=10)
    save(fig, "shap_global.png")

    fig, ax = plt.subplots(figsize=(6, 3.5))
    names = list(comparison)
    means = [comparison[n]["cv"]["pr_auc_mean"] for n in names]
    stds = [comparison[n]["cv"]["pr_auc_std"] for n in names]
    ax.bar(names, means, yerr=stds, color="#7a6fc4", capsize=4)
    ax.set_ylabel("CV PR-AUC (train folds)")
    ax.set_ylim(0, 1)
    ax.set_title("Model comparison" + tag, fontsize=10)
    save(fig, "model_comparison.png")
    return made


def train(
    source: str = "synthetic", seed: int = 42, n_students: int = 1500, out_dir: Path | None = None, quick: bool = False
) -> Path:
    np.random.seed(seed)
    started = datetime.now(UTC)
    ds: Dataset = load_dataset(source, seed=seed, n_students=n_students)
    df = ds.frame
    if len(df) < 200 or df[LABEL_COL].nunique() < 2:
        raise ValueError(f"insufficient data for a credible model: {len(df)} rows")

    train_idx, val_idx, test_idx = grouped_split(df, seed)
    X = df[list(FEATURE_NAMES)].astype(float)
    y = df[LABEL_COL].to_numpy().astype(int)
    g = df[GROUP_COL].to_numpy()
    X_tr, y_tr, g_tr = X.iloc[train_idx], y[train_idx], g[train_idx]
    X_va, y_va = X.iloc[val_idx], y[val_idx]
    X_te, y_te, g_te = X.iloc[test_idx], y[test_idx], g[test_idx]

    leakage = leakage_checks(df, X_tr, y_tr, g_tr, seed)

    comparison: dict[str, dict[str, Any]] = {}
    dummy_cv = cross_val_score(
        DummyClassifier(strategy="prior"),
        X_tr,
        y_tr,
        groups=g_tr,
        scoring="average_precision",
        cv=StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed),
    )
    baseline = {"name": "prior (predicts base rate)", "cv_pr_auc_mean": float(dummy_cv.mean())}
    for name, (pipe, grid) in candidates(seed).items():
        if quick:
            grid = {k: v[:1] for k, v in grid.items()}
        comparison[name] = tune(name, pipe, grid, X_tr, y_tr, g_tr, seed)
        print(
            f"  {name:20s} CV PR-AUC {comparison[name]['cv']['pr_auc_mean']:.4f} "
            f"± {comparison[name]['cv']['pr_auc_std']:.4f}  ({comparison[name]['seconds']}s)",
            flush=True,
        )

    chosen, rule = select_model(comparison)
    pipe, _ = candidates(seed)[chosen]
    pipe.set_params(**comparison[chosen]["raw_params"])
    pipe.fit(X_tr, y_tr)

    calibrated = CalibratedClassifierCV(FrozenEstimator(pipe), method="sigmoid")
    calibrated.fit(X_va, y_va)

    p_va_cal = calibrated.predict_proba(X_va)[:, 1]
    threshold = f1_threshold(y_va, p_va_cal)
    p_te_unc = pipe.predict_proba(X_te)[:, 1]
    p_te_cal = calibrated.predict_proba(X_te)[:, 1]

    test_unc = ranking_metrics(y_te, p_te_unc)
    test_cal = ranking_metrics(y_te, p_te_cal)
    cal_validated = bool(test_cal["ece"] <= ECE_TOLERANCE and test_cal["brier"] <= test_unc["brier"] + 0.002)

    by_sem = []
    for sem in sorted(df.iloc[test_idx]["semester"].unique()):
        mask = (df.iloc[test_idx]["semester"] == sem).to_numpy()
        if mask.sum() >= 30 and 0 < y_te[mask].sum() < mask.sum():
            by_sem.append(
                {
                    "semester": int(sem),
                    "n": int(mask.sum()),
                    "roc_auc": round(float(roc_auc_score(y_te[mask], p_te_cal[mask])), 4),
                    "f1": round(float(f1_score(y_te[mask], (p_te_cal[mask] >= threshold).astype(int))), 4),
                }
            )

    transformed_tr = pipe[:-1].transform(X_tr)
    rng = np.random.default_rng(seed)
    background = transformed_tr[rng.choice(len(transformed_tr), size=min(100, len(transformed_tr)), replace=False)]
    explainer = make_explainer(pipe[-1], background)
    shap_rows = X_te.sample(n=min(600, len(X_te)), random_state=seed)
    importance = global_importance(pipe, explainer, shap_rows)
    perm = permutation_importance(pipe, X_te, y_te, scoring="average_precision", n_repeats=10, random_state=seed, n_jobs=N_JOBS)
    perm_imp = [
        {"feature": f, "label": FEATURE_BY_NAME[f].label, "mean_pr_auc_drop": round(float(m), 5), "std": round(float(s), 5)}
        for f, m, s in sorted(
            zip(FEATURE_NAMES, perm.importances_mean, perm.importances_std, strict=True),
            key=lambda t: -round(float(t[1]), 5),
        )
    ]

    fairness = (
        subgroup_report(df.iloc[test_idx], y_te, p_te_cal, "specialization", threshold)
        if "specialization" in df.columns
        else None
    )

    ranges = {
        f: {
            "min": float(np.nanmin(X_tr[f])),
            "p01": float(np.nanpercentile(X_tr[f], 1)),
            "p99": float(np.nanpercentile(X_tr[f], 99)),
            "max": float(np.nanmax(X_tr[f])),
            "missing_share": round(float(X_tr[f].isna().mean()), 4),
        }
        if X_tr[f].notna().any()
        else None
        for f in FEATURE_NAMES
    }

    import shap
    import sklearn
    import xgboost

    bundle = {
        "pipeline": pipe,
        "calibrated": calibrated,
        "background": background,
        "feature_names_out": list(pipe[:-1].get_feature_names_out()),
    }
    stamp = started.strftime("%Y%m%d%H%M")
    data_tag = "synth" if ds.is_synthetic else "real"
    version = f"readiness-{stamp}-{data_tag}-{chosen.split('_')[0]}-{ds.sha256[:6]}"
    out = (out_dir or BACKEND / "artifacts" / "models") / version
    out.mkdir(parents=True, exist_ok=False)
    model_path = out / "model.joblib"
    joblib.dump(bundle, model_path, compress=3)
    model_sha = hashlib.sha256(model_path.read_bytes()).hexdigest()

    limitations = [
        "Predicts an ASSESSOR'S interview-readiness judgement, not placement or hiring outcomes.",
        "Associations only: SHAP attributions and what-if changes are not causal effects.",
        "Category levels partly rely on self-ratings; inflated self-assessment biases inputs.",
        "Probability bands are only meaningful while calibration remains validated on representative data.",
    ]
    if ds.is_synthetic:
        limitations.insert(
            0,
            "TRAINED AND EVALUATED ON SYNTHETIC DATA: metrics show recovery of a simulated "
            "process and carry NO evidence about real students. Not for real decisions.",
        )

    manifest: dict[str, Any] = {
        "version": version,
        "kind": "readiness_classifier",
        "created_at": started.isoformat(),
        "seed": seed,
        "target": {"name": TARGET_NAME, "definition": TARGET_DEFINITION, "positive_label": "ready"},
        "algorithm": chosen,
        "hyperparameters": comparison[chosen]["params"],
        "feature_schema_hash": schema_hash(),
        "features": [asdict(f) for f in FEATURES],
        "dataset": {
            "source": source,
            "is_synthetic": ds.is_synthetic,
            "sha256": ds.sha256,
            "provenance": ds.provenance,
            "quality": ds.quality,
            "split_method": "StratifiedGroupKFold by student: test 1/7, then validation 1/6 of remainder",
            "splits": {
                "train": _split_summary(df, train_idx),
                "validation": _split_summary(df, val_idx),
                "test": _split_summary(df, test_idx),
            },
        },
        "model_selection": {
            "cv": "5-fold StratifiedGroupKFold on train",
            "primary_metric": "pr_auc",
            "baseline": baseline,
            "candidates": comparison,
            "selected": chosen,
            "rule": rule,
        },
        "calibration": {
            "method": "sigmoid (Platt)",
            "fitted_on": "validation split",
            "validated": cal_validated,
            "criterion": f"test ECE ≤ {ECE_TOLERANCE} and Brier not worse",
            "test_ece_uncalibrated": round(test_unc["ece"], 4),
            "test_ece_calibrated": round(test_cal["ece"], 4),
            "test_brier_uncalibrated": round(test_unc["brier"], 4),
            "test_brier_calibrated": round(test_cal["brier"], 4),
            "reliability_test": reliability_table(y_te, p_te_cal),
        },
        "thresholds": {
            "decision_threshold": round(threshold, 4),
            "decision_threshold_rule": "max F1 on validation",
            "bands": [{"name": n, "low": lo, "high": min(hi, 1.0)} for n, lo, hi in BANDS],
        },
        "metrics": {
            "test_calibrated": {**{k: round(v, 4) for k, v in test_cal.items()}, **point_metrics(y_te, p_te_cal, threshold)},
            "test_calibrated_at_0_5": point_metrics(y_te, p_te_cal, 0.5),
            "test_uncalibrated": {k: round(v, 4) for k, v in test_unc.items()},
            "test_ci95": grouped_bootstrap_ci(y_te, p_te_cal, g_te, threshold, n_boot=200 if quick else 1000, seed=seed),
            "test_bands": band_analysis(y_te, p_te_cal),
            "test_by_semester": by_sem,
        },
        "fairness": fairness,
        "fairness_note": (
            "Subgroups are by academic specialization (synthetic). No protected attributes are "
            "collected or used as features. Gaps are reported, not corrected."
        ),
        "global_importance": importance,
        "permutation_importance_test": perm_imp,
        "training_ranges": ranges,
        "leakage_checks": leakage,
        "libraries": {
            "python": platform.python_version(),
            "scikit-learn": sklearn.__version__,
            "xgboost": xgboost.__version__,
            "shap": shap.__version__,
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
        "limitations": limitations,
        "model_file_sha256": model_sha,
    }
    manifest["figures"] = make_figures(out, y_te, p_te_unc, p_te_cal, threshold, importance, comparison, ds.is_synthetic)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, default=float), encoding="utf-8")
    from ml_pipeline.report import write_report

    write_report(out, manifest)
    print(f"model written: {out}")
    return out


def register(artifact_dir: Path, activate: bool) -> int:
    from app.ml.artifacts import register_artifact

    return register_artifact(artifact_dir, activate)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", default="synthetic", help="synthetic | csv:<path> | app_labels")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--n-students", type=int, default=1500)
    ap.add_argument("--quick", action="store_true", help="tiny grids (tests/CI only)")
    ap.add_argument("--jobs", type=int, default=1, help="parallel workers for CV (default 1 = sequential)")
    ap.add_argument("--register", action="store_true", help="register the artifact in model_versions")
    ap.add_argument("--activate", action="store_true", help="make it the active model (implies --register)")
    args = ap.parse_args(argv)
    global N_JOBS
    N_JOBS = args.jobs
    out = train(args.source, args.seed, args.n_students, quick=args.quick)
    if args.register or args.activate:
        mv_id = register(out, activate=args.activate)
        print(f"registered model_versions.id={mv_id} active={args.activate}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
