# 00 — Executive summary

## What the project is

The **AI Career Guidance App** (formerly *TwinPath AI*) is an explainable, evidence-aware **career digital twin**
for engineering students, with a locally run AI mentor called the **Personalized Mentor**.

A *digital twin* here is a versioned record of one student:

* academic details;
* skills, each on a 0–4 scale;
* projects, internships and certifications, linked to the skills they demonstrate;
* assessment results;
* the verification status of each piece of evidence.

The app compares that record with versioned job-role specifications, estimates whether an assessor would judge the
student *interview-ready*, explains every estimate, lets the student try hypothetical changes safely, and turns the
gaps into an ordered learning roadmap. The mentor answers questions using only the student's own record plus a
curated knowledge base, through a language model that runs on the student's own machine via Ollama.

## Who uses it

| Role | What they do | Where in code |
|---|---|---|
| **Student** | Builds the twin, sees gaps, readiness, simulations, graph, roadmap, mentor, documents; sends feedback | `backend/app/api/v1/twin.py`, `career.py`, `planning.py`, `mentor.py`, `documents.py`; frontend `pages/` |
| **Mentor** (staff) | Sees assigned students **only with their consent**, records verified assessments, verifies evidence, records assessor readiness labels | `backend/app/api/v1/staff.py` `_accessible_student` L44–57 |
| **Admin** | Manages users, mentor links, catalogue, resources, models, knowledge base, retention, audit log, feedback | `backend/app/api/v1/admin.py` (26 operations) |

## What it can do (verified in this audit unless marked)

1. **Accounts and security.**
   * Argon2id password hashing.
   * Server-side sessions stored only as SHA-256 digests.
   * CSRF protection (a per-session token plus a custom header and an Origin allow-list).
   * TOTP two-factor authentication.
   * Lockout with exponential back-off, and rate limits.
   * Role-based access.
   * PostgreSQL **row-level security** on 20 student tables.
   * Data export and hard account deletion.
2. **Evidence-aware digital twin.**
   * Each skill estimate comes from its most trustworthy source: assessed > verified evidence > unverified
     evidence > self-reported. A skill with no information is **unknown, never zero**.
   * Every meaningful change creates a content-addressed snapshot, and versions can be diffed.
3. **Role matching and gap analysis.**
   * A documented weighted formula over 6 roles and 42 skills.
   * Lower and upper match bounds.
   * Gap priorities with prerequisite and multi-role bonuses.
   * A Monte-Carlo test of how stable the role ranking is.
4. **Readiness estimate.**
   * Three algorithms compared (logistic regression, random forest, XGBoost) with student-grouped cross-validation.
   * Logistic regression selected by a pre-stated rule.
   * Platt calibration and SHAP explanations.
   * Out-of-distribution and low-information warnings.
   * A checksum-verified, versioned model registry.
   * **The model is trained on synthetic data and is a demonstration only.**
5. **What-if simulator.** Applies hypothetical changes to a deep copy of the twin and re-runs exactly the same
   pipeline. Nothing is saved to the real profile.
6. **Knowledge graph.** A NetworkX graph of skills, roles, resources, assessments and the student's evidence. Every
   edge is labelled with its provenance (framework, evidence, self-reported or inferred). It drives 3D and accessible
   2D views plus four insight queries.
7. **Roadmap.** Deterministic generation:
   * prerequisite expansion;
   * a priority-aware topological sort;
   * documented effort ranges;
   * weekly scheduling;
   * progress carried over when the plan is regenerated, with a diff against the previous plan.
8. **Personalized Mentor (RAG).**
   * `qwen3:8b` and `nomic-embed-text` run locally through Ollama.
   * Chroma vector store, with each student's private documents filtered to their owner **before** similarity search.
   * Prompt-injection screening, removal of links that aren't in the catalogue, and flagging of unverified
     percentages.
   * Answers stream to the browser as they are generated.
9. **Resume and job-description analysis.** Deterministic: safe parsing, alias-based skill matching, writing
   suggestions, resume-vs-JD comparison.
10. **Feedback collection.** In-app ratings and comments, readable by admins without user identity.
11. **Deployment.** Docker Compose pilot; free-hosting configuration for Vercel, Render and Neon (verified only in a
    local simulation).

## Results measured in this audit (2026-10-21)

| Check | Result |
|---|---|
| Backend tests (pytest, real PostgreSQL 18, least-privilege role with row-level security) | **97 passed** |
| Frontend unit and component tests (Vitest, includes axe accessibility checks) | **26 passed** |
| End-to-end (Playwright, desktop + mobile) | **6 passed** against the dev servers and **6 passed** against the Docker containers |
| Static checks: ruff, ruff format, mypy (80 files), ESLint, `tsc` strict | **Clean** |
| RAG evaluation with the live local models | Retrieval hit@1 **1.00** on 24 questions; generation **9/9** scenarios |
| npm audit (production and development dependencies) | **0 vulnerabilities** |
| pip-audit | **14 advisories in 3 packages** (see below) |
| GitHub Actions on the latest commit `b2fae2a` | **Failed at the dependency-audit step**; the test, lint, type and migration steps passed |

Model metrics come from the bundled artifact's manifest (not re-trained during the audit), on a **synthetic**
held-out test set:

| Metric | Value | 95% CI (clustered by student) |
|---|---|---|
| ROC-AUC | 0.861 | 0.823–0.895 |
| PR-AUC | 0.773 | 0.701–0.843 |
| F1 at threshold 0.413 | 0.705 | 0.640–0.764 |
| Brier score | 0.146 | 0.129–0.164 |
| Expected calibration error | 0.046 | 0.041–0.095 |

These numbers describe how well the model recovers the simulated data-generating process. **They say nothing about
real students.**

## Key findings of this audit

The project is **substantially implemented and well tested**. Most behaviour described in the docs exists in code,
and the main safety claims are backed by tests. The audit found these issues:

| # | Finding | Severity | Detail |
|---|---|---|---|
| F1 | `certifi 2026.7.22` has a newly published advisory (PYSEC-2026-4320; fixed in 2026.10.19). It is a runtime dependency, so it is in the production image | **High (fix now)** | [11-security-review.md](11-security-review.md#dependency-and-container-security) |
| F2 | `pillow 12.3.0` has 8 newly published advisories (fixed in 13.0.0). It arrives only through `matplotlib` in the training group, so it is not in the API image | Medium | same |
| F3 | Because of F1/F2, **CI fails** on the latest commit, and the container scan job is skipped. The README's "pip-audit 0" claim is out of date | Medium | [13-testing-and-quality-assurance.md](13-testing-and-quality-assurance.md#continuous-integration) |
| F4 | No MFA recovery codes, password reset doesn't touch MFA, and admins can't reset MFA, so a lost authenticator means a locked account | Medium | [11-security-review.md](11-security-review.md#mfa-and-account-recovery) |
| F5 | `users`, `user_sessions`, `auth_tokens`, `audit_events` and `mentor_links` have no row-level security; they are protected only by code | Low–Medium (defence in depth) | [10-database-and-data-model.md](10-database-and-data-model.md#row-level-security) |
| F6 | Document parsing runs in a separate process with a timeout, but with no memory limit or OS sandbox | Low–Medium | [14-resume-and-job-description-processing.md](14-resume-and-job-description-processing.md#security-of-uploads) |
| F7 | Five code comments point to documents that don't exist (`docs/methodology/skill-gap.md`, `proficiency.md`, `roadmap.md`, `docs/deployment.md`); a comment cites a nonexistent `bench-argon2` CLI command | Low | [15-project-progress-report.md](15-project-progress-report.md) |
| F8 | Saved what-if scenarios store their inputs, base snapshot and model version, but there is no "replay" endpoint, so they are traceable, not automatically reproducible | Low | [08-digital-twin-roles-and-simulator.md](08-digital-twin-roles-and-simulator.md#reproducibility) |
| F9 | Admin catalogue creation (new roles, skills, prerequisites) exists only in the API; there is no screen for it | Low | [03-backend-code-walkthrough.md](03-backend-code-walkthrough.md#endpoints-without-a-user-interface) |
| F10 | Small code smells: `catalogue_hint()` is never called; an `if True:` block in `mentor.py` L155; the leftover fallback text "The mentor request failed." in `frontend/src/lib/sse.ts` L29 | Cosmetic | — |

## The most important limitations

* **Synthetic model.** The readiness model was never trained or evaluated on real students. It demonstrates the
  method, and the UI says so on every estimate.
* **Readiness is not employability.**
  * The target is an assessor's interview-readiness judgement, not a placement outcome.
  * Match scores compare a profile with an authored framework; they are not hiring probabilities.
* **Expert-judged weights.** Role weights, trust weights, the percentage-to-level mapping and effort ranges are
  documented heuristics, not empirically calibrated.
* **Small, developer-written RAG evaluation set.** The perfect retrieval score is optimistic.
* **Deployment scope.** Single-process rate limiting; no penetration test; free hosting not tested on the real
  services; encryption at rest depends on the host.

## Where to start reading

* For a presentation: [16-presentation-and-viva-guide.md](16-presentation-and-viva-guide.md), then
  [02-system-architecture.md](02-system-architecture.md).
* To extend the code: [03](03-backend-code-walkthrough.md) and [04](04-frontend-code-walkthrough.md), then the
  relevant deep dive.
* To decide what to do next: [15-project-progress-report.md](15-project-progress-report.md).
