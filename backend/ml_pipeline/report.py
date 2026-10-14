"""Renders the evaluation report (report.md) from an executed run's manifest. Every number
in the report comes from the manifest written by the same run."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _f(v: Any, nd: int = 3) -> str:
    return "—" if v is None else (f"{v:.{nd}f}" if isinstance(v, float) else str(v))


def write_report(out: Path, m: dict[str, Any]) -> None:
    t = m["metrics"]["test_calibrated"]
    ci = m["metrics"]["test_ci95"]
    ds = m["dataset"]
    cal = m["calibration"]
    lines: list[str] = []
    w = lines.append
    w(f"# Readiness model evaluation report — `{m['version']}`\n")
    if ds["is_synthetic"]:
        w(
            "> **SYNTHETIC DATA WARNING.** This model was trained and evaluated on a simulated development cohort. "
            "The metrics below measure how well the pipeline recovers a known simulated process. They are **not** "
            "evidence about real students and must not be cited as real-world accuracy.\n"
        )
    w("## Target\n")
    w(f"`{m['target']['name']}` — {m['target']['definition']}\n")
    w("## Data\n")
    w(f"- Source: `{ds['source']}` — {ds['provenance'].get('origin')}")
    w(f"- Dataset SHA-256: `{ds['sha256']}`")
    q = ds["quality"]
    w(
        f"- Rows in/out: {q['rows_in']} → {q['rows_out']} · students: {q['students']} · "
        f"positive rate: {q['positive_rate']:.3f} · snapshots/student: {q['snapshots_per_student']}"
    )
    w(
        f"- Removed: {q['invalid_label_rows']} invalid labels, {q['range_violation_rows']} out-of-range rows, "
        f"{q['exact_duplicates_removed']} exact duplicates; conflicting-label snapshots: {q['conflicting_label_snapshots']}"
    )
    w(f"- Split ({ds['split_method']}):\n")
    w("| split | rows | students | positive rate |\n|---|---:|---:|---:|")
    for k, s in ds["splits"].items():
        w(f"| {k} | {s['rows']} | {s['students']} | {s['positive_rate']:.3f} |")
    w("\n## Model selection (cross-validation on the training split only)\n")
    sel = m["model_selection"]
    w(f"Baseline — {sel['baseline']['name']}: CV PR-AUC {sel['baseline']['cv_pr_auc_mean']:.3f}\n")
    w("| candidate | best params | CV PR-AUC | CV ROC-AUC | CV log-loss | CV Brier |\n|---|---|---:|---:|---:|---:|")
    for name, c in sel["candidates"].items():
        cv = c["cv"]
        w(
            f"| {name}{' **(selected)**' if name == sel['selected'] else ''} | `{c['params']}` | "
            f"{cv['pr_auc_mean']:.3f} ± {cv['pr_auc_std']:.3f} | {cv['roc_auc_mean']:.3f} | "
            f"{cv['log_loss_mean']:.3f} | {cv['brier_mean']:.3f} |"
        )
    w(f"\nSelection rule: {sel['rule']}\n")
    w("## Held-out test results (evaluated once)\n")
    w(
        f"Decision threshold {t['threshold']:.3f} ({m['thresholds']['decision_threshold_rule']}). "
        "95% CIs from a 1,000-sample student-clustered bootstrap.\n"
    )
    w("| metric | value | 95% CI |\n|---|---:|---|")
    for key, label in (("roc_auc", "ROC-AUC"), ("pr_auc", "PR-AUC"), ("brier", "Brier score"), ("ece", "ECE"), ("f1", "F1")):
        c = ci.get(key)
        w(f"| {label} | {t[key]:.3f} | {f'{c["low"]:.3f} – {c["high"]:.3f}' if c else '—'} |")
    for key, label in (
        ("accuracy", "Accuracy"),
        ("precision", "Precision"),
        ("recall", "Recall"),
        ("specificity", "Specificity"),
        ("log_loss", "Log-loss"),
        ("prevalence", "Prevalence"),
    ):
        w(f"| {label} | {_f(t.get(key))} | — |")
    cm = t["confusion_matrix"]
    w(f"\nConfusion matrix @ threshold: TN {cm['tn']} · FP {cm['fp']} · FN {cm['fn']} · TP {cm['tp']}\n")
    w("## Calibration\n")
    w(
        f"Method: {cal['method']} fitted on the {cal['fitted_on']}. Test ECE {cal['test_ece_uncalibrated']} → "
        f"{cal['test_ece_calibrated']}; Brier {cal['test_brier_uncalibrated']} → {cal['test_brier_calibrated']}. "
        f"**Calibration validated: {cal['validated']}** ({cal['criterion']}).\n"
    )
    w("| band | probability range | test share | observed ready rate |\n|---|---|---:|---:|")
    for b in m["metrics"]["test_bands"]:
        w(f"| {b['band']} | {b['range'][0]:.2f}–{b['range'][1]:.2f} | {b['share']:.3f} | {_f(b['observed_ready_rate'])} |")
    if m["metrics"]["test_by_semester"]:
        w("\n## Temporal slices (test)\n")
        w("| semester | n | ROC-AUC | F1 |\n|---:|---:|---:|---:|")
        for s in m["metrics"]["test_by_semester"]:
            w(f"| {s['semester']} | {s['n']} | {s['roc_auc']:.3f} | {s['f1']:.3f} |")
    w("\n## Explainability\n")
    w("Global mean |SHAP| on the test split (aggregated over value + missing-indicator):\n")
    w("| feature | mean abs SHAP | mean SHAP |\n|---|---:|---:|")
    for gi in m["global_importance"][:12]:
        w(f"| {gi['label']} | {gi['mean_abs_shap']:.4f} | {gi['mean_shap']:+.4f} |")
    w("\nPermutation importance (drop in test PR-AUC), as an independent cross-check:\n")
    w("| feature | PR-AUC drop | std |\n|---|---:|---:|")
    for pi in m["permutation_importance_test"][:10]:
        w(f"| {pi['label']} | {pi['mean_pr_auc_drop']:.4f} | {pi['std']:.4f} |")
    w("\n## Leakage checks\n")
    lk = m["leakage_checks"]
    w(f"- Students shared between splits: {lk['students_shared_between_splits']}")
    w(f"- Preprocessing fitted within CV folds: {lk['preprocessing_fitted_within_cv_folds']}")
    w(f"- Shuffled-label CV ROC-AUC: {lk['shuffled_label_cv_roc_auc']} (sanity passed: {lk['shuffled_label_sanity_passed']})")
    w(f"- Max |feature–label correlation|: {lk['max_abs_feature_label_correlation']}")
    w(f"- {lk['temporal_note']}")
    if m.get("fairness"):
        fr = m["fairness"]
        w(f"\n## Subgroup report ({fr['group_column']})\n")
        w(m["fairness_note"] + "\n")
        w("| group | n | base rate | selection rate | TPR | FPR | ROC-AUC | ECE |\n|---|---:|---:|---:|---:|---:|---:|---:|")
        for gr in fr["groups"]:
            w(
                f"| {gr['group']} | {gr['n']} | {gr['base_rate']:.3f} | {gr['selection_rate']:.3f} | {_f(gr.get('tpr'))} | "
                f"{_f(gr.get('fpr'))} | {_f(gr.get('roc_auc'))} | {_f(gr.get('ece'))} |"
            )
        w(f"\nLargest between-group gaps: {fr['max_gaps']}\n")
    w("## Limitations\n")
    for lim in m["limitations"]:
        w(f"- {lim}")
    w("\n## Reproducibility\n")
    w(
        f"Seed {m['seed']} · libraries {m['libraries']} · model file SHA-256 `{m['model_file_sha256']}` · "
        f"feature schema `{m['feature_schema_hash']}`.\n"
    )
    w("Figures: " + ", ".join(f"[{f}]({f})" for f in m.get("figures", [])))
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
