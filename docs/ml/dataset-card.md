# Dataset card — readiness model data sources

## Why synthetic data exists

No legitimate, consented, assessor-labelled dataset of engineering students with the required features was
available. Rather than inventing labels and presenting a "placement model", the pipeline was built on a clearly
labelled **synthetic development cohort** so that every stage (validation, splitting, tuning, calibration,
explanation, fairness reporting, inference, simulation) could be implemented and tested end to end. The
interfaces for real data are implemented and documented below.

## Source 1 — `synthetic` (active model)

| Property | Value |
|---|---|
| Generator | `ml_pipeline/synthetic.py`, version `synthetic-cohort-v1` |
| Size (active model) | 1,500 simulated students, 3,019 snapshots (1–3 per student, semesters 5–8) |
| Seed | 42 (fully deterministic; dataset SHA-256 recorded in the manifest) |
| Positive rate | 0.361 |
| Personal data | none — no real person is represented |
| Licence/permission | not applicable |

**Generative process (design choices, not empirical facts):**

* Per student: aptitude *a*, diligence *d*, communication *k* ~ N(0,1); a focus area (software / data / ML / web)
  and a specialization (CSE 40%, IT 25%, AI-DS 20%, ECE 15%).
* Per snapshot: progress *p* = (semester − 5)/3; latent competency *c* = 0.6a + 0.5d + 0.6p + N(0, 0.3²).
* Observed features are noisy, partially missing proxies of the latents: category levels are missing more often
  outside the focus area, and **self-ratings are inflated when evidence strength is low**. Assessments are missing
  for 35–75% of rows, and CGPA for 5%.
* Label: z = 1.4c + 0.5k + 0.3·[has a deployed project] + N(0, 0.6²); "ready" if z is above its 65th percentile, then
  5% of labels are flipped to model assessor inconsistency.

**Consequences.** The achievable ceiling is limited by the label noise and by latents that are only partly observed.
The model's ranking of feature importance reflects these coefficients and has **no meaning for real students**.

## Source 2 — `app_labels` (implemented, no data yet)

Assessor labels recorded in TwinPath (`readiness_labels`), each frozen against the twin snapshot it was given
against, so features can never contain later information. Only students who currently grant the **research-use**
consent are exported. The specialization column is used for subgroup reporting only.

## Source 3 — `csv:<path>` (implemented)

A historical or externally collected CSV with the schema columns. Training **refuses to run** unless a sidecar
`<file>.provenance.json` provides `origin`, `permission`, `label_definition`, `collection_period` and `contact`.
Columns that look like protected or identifying attributes (name, email, gender, religion, caste, date of birth…)
cause the import to fail.

## Quality checks applied to every source

Schema and required columns; numeric coercion; invalid labels removed; rows outside documented feature ranges
removed and counted per feature; exact duplicates removed; conflicting labels for the same student and semester
counted; missing share reported per feature; IQR×3 outliers **reported, not removed**; students, positive rate and
snapshots per student reported. All counts are written to the manifest and the run report.
