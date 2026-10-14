"""SHAP explanations for the readiness model (shared by training and inference).

* Explanations are computed on the UNCALIBRATED pipeline (imputer → [scaler] → estimator)
  in the model's raw output space (log-odds for logistic regression / XGBoost, probability
  for random forests); the space is reported with every explanation.
* Contributions of a feature's value and its missing-indicator are summed back to the
  original feature, so "unknown" inputs are explained explicitly.
* SHAP attributions describe how the MODEL used its inputs. They are not causal effects.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
import shap
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression

from app.ml.feature_schema import FEATURE_BY_NAME, FEATURE_NAMES

MISSING_PREFIX = "missingindicator_"


def output_space(estimator: Any) -> str:
    return "probability" if isinstance(estimator, RandomForestClassifier) else "log_odds"


def make_explainer(estimator: Any, background: np.ndarray) -> Any:
    if isinstance(estimator, LogisticRegression):
        return shap.LinearExplainer(estimator, background)
    return shap.TreeExplainer(estimator, data=background, feature_perturbation="interventional")


def _class1(values: np.ndarray) -> np.ndarray:
    return values[..., 1] if values.ndim == 3 else values


def shap_matrix(pipeline: Any, explainer: Any, X: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, list[str]]:
    transformed = pipeline[:-1].transform(X)
    names = list(pipeline[:-1].get_feature_names_out())
    explanation = explainer(transformed)
    values = _class1(np.asarray(explanation.values))
    base = np.asarray(explanation.base_values)
    base = base[..., 1] if base.ndim == 2 else base
    return values, base, names


def aggregate_to_features(values: np.ndarray, names: list[str]) -> np.ndarray:
    """(n, transformed) -> (n, len(FEATURE_NAMES)) by summing indicator columns into their base."""
    out = np.zeros((values.shape[0], len(FEATURE_NAMES)))
    index = {f: i for i, f in enumerate(FEATURE_NAMES)}
    for j, name in enumerate(names):
        base = name[len(MISSING_PREFIX) :] if name.startswith(MISSING_PREFIX) else name
        if base in index:
            out[:, index[base]] += values[:, j]
    return out


def global_importance(pipeline: Any, explainer: Any, X: pd.DataFrame) -> list[dict[str, Any]]:
    values, _, names = shap_matrix(pipeline, explainer, X)
    agg = aggregate_to_features(values, names)
    mean_abs = np.abs(agg).mean(axis=0)
    mean_signed = agg.mean(axis=0)
    order = np.argsort(-mean_abs)
    return [
        {
            "feature": FEATURE_NAMES[i],
            "label": FEATURE_BY_NAME[FEATURE_NAMES[i]].label,
            "mean_abs_shap": round(float(mean_abs[i]), 5),
            "mean_shap": round(float(mean_signed[i]), 5),
        }
        for i in order
    ]


def _fmt_value(name: str, value: float | None) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "unknown"
    spec = FEATURE_BY_NAME[name]
    if spec.integer:
        return f"{int(value)}"
    if spec.unit == "%":
        return f"{value:.0f}%"
    if spec.unit in ("/4", "/10"):
        return f"{value:.1f}{spec.unit}"
    if name == "evidence_strength":
        return f"{value:.0%}"
    return f"{value:g} {spec.unit}".strip()


def explain_single(pipeline: Any, explainer: Any, features: dict[str, float | None], top_k: int = 8) -> dict[str, Any]:
    X = pd.DataFrame(
        [[np.nan if features[f] is None else features[f] for f in FEATURE_NAMES]], columns=list(FEATURE_NAMES), dtype=float
    )
    values, base, names = shap_matrix(pipeline, explainer, X)
    agg = aggregate_to_features(values, names)[0]
    contribs: list[dict[str, Any]] = []
    for i, name in enumerate(FEATURE_NAMES):
        val = features[name]
        contribs.append(
            {
                "feature": name,
                "label": FEATURE_BY_NAME[name].label,
                "value": val,
                "display_value": _fmt_value(name, val),
                "is_missing": val is None,
                "contribution": round(float(agg[i]), 5),
                "direction": "raises" if agg[i] > 0 else ("lowers" if agg[i] < 0 else "neutral"),
            }
        )
    contribs.sort(key=lambda c: -abs(c["contribution"]))
    return {
        "output_space": output_space(pipeline[-1]),
        "base_value": round(float(base[0]), 5),
        "contributions": contribs,
        "top": contribs[:top_k],
        "sum_check": round(float(base[0] + agg.sum()), 5),
    }
