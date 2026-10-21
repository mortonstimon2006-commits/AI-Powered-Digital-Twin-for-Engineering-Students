# Readiness model evaluation report — `readiness-202610141151-synth-logistic-d41952`

> **SYNTHETIC DATA WARNING.** This model was trained and evaluated on a simulated development cohort. The metrics below measure how well the pipeline recovers a known simulated process. They are **not** evidence about real students and must not be cited as real-world accuracy.

## Target

`assessor_interview_ready` — Binary label recorded by a qualified assessor (mentor/faculty) after a structured review: 1 = the student is judged ready to interview for an entry-level technical role, 0 = not yet. It is NOT a placement or hiring outcome and must not be presented as one.

## Data

- Source: `synthetic` — Simulated by synthetic-cohort-v1 (seed=42, n_students=1500)
- Dataset SHA-256: `d41952193e8e5e48e95209cdaf9d013f19cff7c057819d1c8c52a517b54bf859`
- Rows in/out: 3019 → 3019 · students: 1500 · positive rate: 0.361 · snapshots/student: 2.01
- Removed: 0 invalid labels, 0 out-of-range rows, 0 exact duplicates; conflicting-label snapshots: 0
- Split (StratifiedGroupKFold by student: test 1/7, then validation 1/6 of remainder):

| split | rows | students | positive rate |
|---|---:|---:|---:|
| train | 2155 | 1058 | 0.361 |
| validation | 432 | 221 | 0.361 |
| test | 432 | 221 | 0.361 |

## Model selection (cross-validation on the training split only)

Baseline — prior (predicts base rate): CV PR-AUC 0.361

| candidate | best params | CV PR-AUC | CV ROC-AUC | CV log-loss | CV Brier |
|---|---|---:|---:|---:|---:|
| logistic_regression **(selected)** | `{'C': 0.01, 'class_weight': None}` | 0.768 ± 0.015 | 0.846 | 0.463 | 0.152 |
| random_forest | `{'max_depth': 8, 'min_samples_leaf': 1}` | 0.759 ± 0.016 | 0.843 | 0.472 | 0.154 |
| xgboost | `{'learning_rate': 0.03, 'max_depth': 2, 'min_child_weight': 1}` | 0.759 ± 0.019 | 0.841 | 0.468 | 0.154 |

Selection rule: Highest mean CV PR-AUC was logistic_regression (0.7680 ± SE 0.0067). Candidates within one standard error: ['logistic_regression']; the simplest (logistic_regression) was selected.

## Held-out test results (evaluated once)

Decision threshold 0.413 (max F1 on validation). 95% CIs from a 1,000-sample student-clustered bootstrap.

| metric | value | 95% CI |
|---|---:|---|
| ROC-AUC | 0.861 | 0.823 – 0.895 |
| PR-AUC | 0.773 | 0.701 – 0.843 |
| Brier score | 0.146 | 0.129 – 0.164 |
| ECE | 0.045 | 0.041 – 0.095 |
| F1 | 0.705 | 0.640 – 0.764 |
| Accuracy | 0.785 | — |
| Precision | 0.698 | — |
| Recall | 0.712 | — |
| Specificity | 0.826 | — |
| Log-loss | 0.450 | — |
| Prevalence | 0.361 | — |

Confusion matrix @ threshold: TN 228 · FP 48 · FN 45 · TP 111

## Calibration

Method: sigmoid (Platt) fitted on the validation split. Test ECE 0.0426 → 0.0455; Brier 0.145 → 0.1457. **Calibration validated: True** (test ECE ≤ 0.05 and Brier not worse).

| band | probability range | test share | observed ready rate |
|---|---|---:|---:|
| not_yet_ready | 0.00–0.35 | 0.553 | 0.126 |
| developing | 0.35–0.65 | 0.266 | 0.513 |
| interview_ready | 0.65–1.00 | 0.181 | 0.859 |

## Temporal slices (test)

| semester | n | ROC-AUC | F1 |
|---:|---:|---:|---:|
| 5 | 110 | 0.840 | 0.632 |
| 6 | 115 | 0.888 | 0.785 |
| 7 | 101 | 0.846 | 0.700 |
| 8 | 106 | 0.856 | 0.687 |

## Explainability

Global mean |SHAP| on the test split (aggregated over value + missing-indicator):

| feature | mean abs SHAP | mean SHAP |
|---|---:|---:|
| CGPA | 0.2270 | -0.0391 |
| Programming level | 0.1974 | -0.0056 |
| Evidence strength | 0.1913 | -0.0032 |
| Mock interview | 0.1762 | +0.0738 |
| Data analysis level | 0.1727 | -0.0095 |
| Coding assessment | 0.1715 | -0.0302 |
| Deployed projects | 0.1631 | -0.0299 |
| Communication assessment | 0.1528 | -0.0225 |
| Databases level | 0.1401 | -0.0084 |
| DSA level | 0.1302 | -0.0221 |
| Web development level | 0.1038 | -0.0203 |
| Semester | 0.0908 | -0.0189 |

Permutation importance (drop in test PR-AUC), as an independent cross-check:

| feature | PR-AUC drop | std |
|---|---:|---:|
| Mock interview | 0.0206 | 0.0060 |
| Communication assessment | 0.0183 | 0.0067 |
| Data analysis level | 0.0166 | 0.0066 |
| CGPA | 0.0155 | 0.0063 |
| Evidence strength | 0.0140 | 0.0046 |
| Programming level | 0.0106 | 0.0073 |
| Deployed projects | 0.0095 | 0.0087 |
| Databases level | 0.0049 | 0.0054 |
| Coding assessment | 0.0048 | 0.0080 |
| Web development level | 0.0048 | 0.0031 |

## Leakage checks

- Students shared between splits: 0
- Preprocessing fitted within CV folds: True
- Shuffled-label CV ROC-AUC: 0.5075 (sanity passed: True)
- Max |feature–label correlation|: 0.4551
- Each label is paired with features from the same snapshot; no later information is used.

## Subgroup report (specialization)

Subgroups are by academic specialization (synthetic). No protected attributes are collected or used as features. Gaps are reported, not corrected.

| group | n | base rate | selection rate | TPR | FPR | ROC-AUC | ECE |
|---|---:|---:|---:|---:|---:|---:|---:|
| AI-DS | 91 | 0.319 | 0.418 | 0.828 | 0.226 | 0.862 | 0.112 |
| CSE | 176 | 0.369 | 0.347 | 0.646 | 0.171 | 0.845 | 0.055 |
| ECE | 52 | 0.288 | 0.269 | 0.667 | 0.108 | 0.845 | 0.162 |
| IT | 113 | 0.416 | 0.407 | 0.745 | 0.167 | 0.895 | 0.112 |

Largest between-group gaps: {'tpr': 0.1814, 'fpr': 0.1177, 'roc_auc': 0.0502, 'ece': 0.1063, 'selection_rate': 0.1484}

## Limitations

- TRAINED AND EVALUATED ON SYNTHETIC DATA: metrics show recovery of a simulated process and carry NO evidence about real students. Not for real decisions.
- Predicts an ASSESSOR'S interview-readiness judgement, not placement or hiring outcomes.
- Associations only: SHAP attributions and what-if changes are not causal effects.
- Category levels partly rely on self-ratings; inflated self-assessment biases inputs.
- Probability bands are only meaningful while calibration remains validated on representative data.

## Reproducibility

Seed 42 · libraries {'python': '3.12.10', 'scikit-learn': '1.9.1', 'xgboost': '3.4.1', 'shap': '0.53.0', 'numpy': '2.5.4', 'pandas': '3.0.6'} · model file SHA-256 `5aa682f819ab744d1a9202f6003c3d63d862d08b61ed5efc2b781a2b3703745a` · feature schema `a5e3d6b62297d19e`.

Figures: [figures/roc.png](figures/roc.png), [figures/pr.png](figures/pr.png), [figures/calibration.png](figures/calibration.png), [figures/confusion.png](figures/confusion.png), [figures/shap_global.png](figures/shap_global.png), [figures/model_comparison.png](figures/model_comparison.png)
