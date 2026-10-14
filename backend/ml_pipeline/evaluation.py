"""Evaluation utilities: metrics, grouped bootstrap confidence intervals, calibration
(ECE / reliability), band analysis and subgroup (fairness) reporting."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)

BANDS = (("not_yet_ready", 0.0, 0.35), ("developing", 0.35, 0.65), ("interview_ready", 0.65, 1.0001))


def band_for(p: float) -> str:
    for name, lo, hi in BANDS:
        if lo <= p < hi:
            return name
    return BANDS[-1][0]


def expected_calibration_error(y: np.ndarray, p: np.ndarray, n_bins: int = 10) -> float:
    bins = np.linspace(0, 1, n_bins + 1)
    idx = np.clip(np.digitize(p, bins[1:-1]), 0, n_bins - 1)
    ece = 0.0
    for b in range(n_bins):
        mask = idx == b
        if mask.any():
            ece += mask.mean() * abs(y[mask].mean() - p[mask].mean())
    return float(ece)


def reliability_table(y: np.ndarray, p: np.ndarray, n_bins: int = 10) -> list[dict[str, float]]:
    bins = np.linspace(0, 1, n_bins + 1)
    idx = np.clip(np.digitize(p, bins[1:-1]), 0, n_bins - 1)
    out = []
    for b in range(n_bins):
        mask = idx == b
        if mask.sum() >= 1:
            out.append(
                {
                    "bin_low": round(float(bins[b]), 2),
                    "bin_high": round(float(bins[b + 1]), 2),
                    "n": int(mask.sum()),
                    "mean_predicted": round(float(p[mask].mean()), 4),
                    "observed_rate": round(float(y[mask].mean()), 4),
                }
            )
    return out


def point_metrics(y: np.ndarray, p: np.ndarray, threshold: float) -> dict[str, Any]:
    yhat = (p >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, yhat, labels=[0, 1]).ravel()
    return {
        "threshold": round(float(threshold), 4),
        "accuracy": float(accuracy_score(y, yhat)),
        "precision": float(precision_score(y, yhat, zero_division=0)),
        "recall": float(recall_score(y, yhat, zero_division=0)),
        "f1": float(f1_score(y, yhat, zero_division=0)),
        "specificity": float(tn / (tn + fp)) if (tn + fp) else None,
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
    }


def ranking_metrics(y: np.ndarray, p: np.ndarray) -> dict[str, float]:
    return {
        "roc_auc": float(roc_auc_score(y, p)),
        "pr_auc": float(average_precision_score(y, p)),
        "brier": float(brier_score_loss(y, p)),
        "log_loss": float(log_loss(y, np.clip(p, 1e-6, 1 - 1e-6))),
        "ece": expected_calibration_error(y, p),
        "prevalence": float(y.mean()),
    }


def grouped_bootstrap_ci(
    y: np.ndarray, p: np.ndarray, groups: np.ndarray, threshold: float, n_boot: int = 1000, seed: int = 0
) -> dict[str, dict[str, float]]:
    """Cluster bootstrap over students (rows of one student are resampled together)."""
    rng = np.random.default_rng(seed)
    uniq = np.unique(groups)
    members = {g: np.flatnonzero(groups == g) for g in uniq}
    stats: dict[str, list[float]] = {k: [] for k in ("roc_auc", "pr_auc", "brier", "f1", "ece")}
    for _ in range(n_boot):
        pick = rng.choice(uniq, size=len(uniq), replace=True)
        idx = np.concatenate([members[g] for g in pick])
        yb, pb = y[idx], p[idx]
        if yb.min() == yb.max():
            continue
        stats["roc_auc"].append(roc_auc_score(yb, pb))
        stats["pr_auc"].append(average_precision_score(yb, pb))
        stats["brier"].append(brier_score_loss(yb, pb))
        stats["f1"].append(f1_score(yb, (pb >= threshold).astype(int), zero_division=0))
        stats["ece"].append(expected_calibration_error(yb, pb))
    return {
        k: {"low": round(float(np.percentile(v, 2.5)), 4), "high": round(float(np.percentile(v, 97.5)), 4)}
        for k, v in stats.items()
        if v
    }


def band_analysis(y: np.ndarray, p: np.ndarray) -> list[dict[str, Any]]:
    out = []
    for name, lo, hi in BANDS:
        mask = (p >= lo) & (p < hi)
        out.append(
            {
                "band": name,
                "range": [lo, min(hi, 1.0)],
                "n": int(mask.sum()),
                "share": round(float(mask.mean()), 4),
                "observed_ready_rate": round(float(y[mask].mean()), 4) if mask.any() else None,
            }
        )
    return out


def subgroup_report(
    df: pd.DataFrame, y: np.ndarray, p: np.ndarray, group_col: str, threshold: float, min_n: int = 30
) -> dict[str, Any]:
    rows = []
    for g in sorted(df[group_col].astype(str).unique()):
        mask = (df[group_col].astype(str) == g).to_numpy()
        n = int(mask.sum())
        yg, pg = y[mask], p[mask]
        entry: dict[str, Any] = {"group": g, "n": n, "positives": int(yg.sum()), "base_rate": round(float(yg.mean()), 4)}
        yhat = (pg >= threshold).astype(int)
        entry["selection_rate"] = round(float(yhat.mean()), 4)
        if n >= min_n and 0 < yg.sum() < n:
            tn, fp, fn, tp = confusion_matrix(yg, yhat, labels=[0, 1]).ravel()
            entry.update(
                {
                    "tpr": round(float(tp / (tp + fn)), 4) if (tp + fn) else None,
                    "fpr": round(float(fp / (fp + tn)), 4) if (fp + tn) else None,
                    "roc_auc": round(float(roc_auc_score(yg, pg)), 4),
                    "ece": round(expected_calibration_error(yg, pg), 4),
                    "sufficient_n": True,
                }
            )
        else:
            entry["sufficient_n"] = False
        rows.append(entry)
    valid = [r for r in rows if r.get("sufficient_n")]
    gaps = {}
    for metric in ("tpr", "fpr", "roc_auc", "ece", "selection_rate"):
        vals = [r[metric] for r in valid if r.get(metric) is not None]
        if len(vals) >= 2:
            gaps[metric] = round(max(vals) - min(vals), 4)
    return {"group_column": group_col, "threshold": threshold, "min_n_for_metrics": min_n, "groups": rows, "max_gaps": gaps}
