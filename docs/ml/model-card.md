# Model card — AI Career Guidance App readiness classifier

> **Status: DEMONSTRATION MODEL — trained and evaluated on synthetic data.**
> Every number below measures how well the pipeline recovers a *simulated* process
> ([dataset card](dataset-card.md)). None of it is evidence about real students, and none of it may be cited
> as real-world accuracy. The application shows this warning next to every estimate.

| Field | Value |
|---|---|
| Version | `readiness-202610141151-synth-logistic-d41952` |
| Kind | binary classifier, versioned artifact (`model.joblib` + `manifest.json`) |
| Algorithm | logistic regression (C = 0.01, no class weighting) inside an imputer → scaler pipeline |
| Output | calibrated probability (Platt scaling) → band; SHAP attributions in log-odds |
| Artifact SHA-256 | `5aa682f819ab744d…` (full hash in the manifest and in `model_versions`) |
| Feature schema hash | `a5e3d6b62297d19e` (loading fails if the code's feature contract differs) |
| Libraries | Python 3.12.10 · scikit-learn 1.9.1 · XGBoost 3.4.1 · SHAP 0.53.0 · NumPy 2.5.4 · pandas 3.0.6 |
| Reproduce | `uv run python -m ml_pipeline.train --source synthetic --seed 42 --n-students 1500` (identical CV/test metrics on re-run) |

## Intended use

* **Target (`assessor_interview_ready`)** — a qualified assessor's structured judgement that a student is ready to
  interview for an entry-level technical role. **It is not a placement, hiring or employability prediction.**
* Used to give students an explained, uncertainty-aware estimate and to compare what-if scenarios.
* **Out of scope:** admissions, ranking students against each other, any decision with consequences for a
  student, or any claim about future employment.

## Inputs (19 features, all may be "unknown")

CGPA, semester, eight evidence-weighted category levels (programming, DSA, databases, web, AI/ML, data,
cloud/DevOps, security), evidence strength, projects, deployed projects, internship months, verified
certifications, hackathons, and the latest *verified* coding, communication and mock-interview scores.
Unknown values are imputed with an explicit missing-indicator, so "unknown" is never silently treated as zero.
No protected attributes are collected or used.

## Training protocol (pre-specified)

1. Grouped, stratified split **by student**: train 2,155 rows / 1,058 students, validation 432 / 221,
   test 432 / 221 (positive rate 0.361 in each). No student appears in more than one split.
2. 5-fold `StratifiedGroupKFold` CV on train only; preprocessing fitted inside each fold.
3. Candidates and CV PR-AUC (mean ± sd): logistic regression **0.768 ± 0.015**, random forest 0.759 ± 0.016,
   XGBoost 0.759 ± 0.019; prior baseline 0.361. Selection rule: best mean PR-AUC, simpler model preferred within
   one standard error → logistic regression (XGBoost was *not* better on this data).
4. Platt calibration fitted on validation; decision threshold (0.413) chosen on validation (max F1).
5. **Evaluated once on the held-out test split.**

## Held-out test results (n = 432, 221 students; 95% CI = student-clustered bootstrap, 1,000 resamples)

| Metric | Value | 95% CI |
|---|---:|---|
| ROC-AUC | 0.861 | 0.823 – 0.895 |
| PR-AUC | 0.773 | 0.701 – 0.843 |
| F1 (threshold 0.413) | 0.705 | 0.640 – 0.764 |
| Brier score | 0.146 | 0.129 – 0.164 |
| ECE (10 bins) | 0.046 | 0.041 – 0.095 |
| Accuracy / precision / recall / specificity | 0.785 / 0.698 / 0.712 / 0.826 | — |

Confusion matrix: TN 228 · FP 48 · FN 45 · TP 111.

**Calibration.** Test ECE 0.043 (uncalibrated) → 0.046 (Platt); Brier 0.145 → 0.146. The pre-registered criterion
(ECE ≤ 0.05 and Brier not worse by more than 0.002) is met, so the UI shows probabilities rounded to the nearest
5%. Logistic regression was already well calibrated; Platt scaling did not improve it. Observed "ready" rates per
band on test: not-yet-ready 0.13 · developing 0.51 · interview-ready 0.86.

**Temporal slices (test).** ROC-AUC by semester: 5 → 0.840, 6 → 0.888, 7 → 0.846, 8 → 0.856.

## Explainability

* Local explanations: SHAP `LinearExplainer` on the uncalibrated pipeline (log-odds space), value and
  missing-indicator contributions summed per feature. Additivity is verified in tests (base + Σ contributions =
  model log-odds).
* Global mean |SHAP| (test): CGPA 0.227 · programming level 0.197 · evidence strength 0.191 · mock interview 0.176
  · data-analysis level 0.173 · coding assessment 0.171. Permutation importance is reported in the run report as
  an independent cross-check.
* Attributions describe the **model**, not causes. The UI states this beside every explanation.

## Subgroup report (specialization; synthetic groups; no protected attributes)

| Group | n | TPR | FPR | ROC-AUC | ECE |
|---|---:|---:|---:|---:|---:|
| AI-DS | 91 | 0.83 | 0.23 | 0.86 | 0.11 |
| CSE | 176 | 0.65 | 0.17 | 0.85 | 0.06 |
| ECE | 52 | 0.67 | 0.11 | 0.85 | 0.16 |
| IT | 113 | 0.74 | 0.17 | 0.90 | 0.11 |

Largest gaps: TPR 0.18, FPR 0.12, ECE 0.11. Groups are small, so these are noisy; **no claim of being unbiased is
made.** On real data, subgroup evaluation must be repeated only where lawful, consented and adequately powered.

## Leakage checks (all passed)

Students shared between splits: 0 · preprocessing fitted within CV folds · shuffled-label CV ROC-AUC 0.508 (≈ chance)
· maximum |feature–label correlation| 0.455 · no identifier-like features · labels are paired only with features from
the same snapshot.

## Runtime safeguards

Checksum-verified loading (joblib is never loaded unverified) · feature-schema and library-version checks · input
range validation · out-of-distribution warnings when a value is outside the training 1st–99th percentile · a
low-information warning when < 50% of inputs are known · explicit "model unavailable" instead of any fallback.

## Path to a real model

1. Assessors record labels in-app (Mentor tools → readiness label); each label is frozen against a twin snapshot.
2. Only students who grant **research use** consent are exported (`--source app_labels`).
3. Alternatively import a historical CSV with a mandatory provenance file (`--source csv:<path>`).
4. Re-run the identical protocol; activate only after reviewing the generated report.
   Minimum suggested size before any pilot use: several hundred labelled students per role family.
