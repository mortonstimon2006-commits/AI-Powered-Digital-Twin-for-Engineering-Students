# Status, acceptance criteria and known limitations (2026-10-14)

## Definition-of-Done checklist

| # | Criterion | Status | Evidence / remaining work |
|---|---|---|---|
| 1 | Frontend builds | **VERIFIED** | `npm run build` (Vite 8); container image builds |
| 2 | Backend starts | **VERIFIED** | uvicorn (native) and the `api` container; `/api/v1/health/ready` = ok |
| 3 | Migrations from a clean environment | **VERIFIED** | tests run `downgrade base → upgrade head` on every session; CI does up/down/up + `alembic check` |
| 4 | Authentication works | **VERIFIED** | 19 auth tests; Playwright register → login → deletion |
| 5 | No cross-student data access | **VERIFIED** (automated) | IDOR tests on every resource type + raw-SQL RLS tests under the app role; not pen-tested |
| 6 | Twin persists real updates | **VERIFIED** | snapshot/diff tests; end-to-end onboarding |
| 7 | Predictions from a versioned model, or explicit "unavailable" | **VERIFIED** | registry checks; `test_readiness_unavailable_without_model` |
| 8 | Metrics from an executed, documented evaluation | **VERIFIED** — synthetic data only | [model card](ml/model-card.md); no real-student evaluation exists |
| 9 | SHAP corresponds to the selected model | **VERIFIED** | additivity test (base + Σ = model log-odds) |
| 10 | Roles use a real, documented framework | **VERIFIED** — framework not externally validated | [role framework](methodology/role-framework.md) |
| 11 | Simulator does not corrupt the profile | **VERIFIED** | `test_simulation_never_touches_real_twin` |
| 12 | Roadmaps from real gaps and permitted resources | **VERIFIED** | roadmap tests; link-validated catalogue |
| 13 | Mentor uses local Ollama | **VERIFIED** | live runs with qwen3:8b; no external LLM code paths exist |
| 14 | RAG relevant and access-controlled | **VERIFIED** on the in-house set | owner-scoping tests; eval hit@1 = 1.0 (optimistic, see report) |
| 15 | Uploads validated and handled securely | **VERIFIED** | malicious-file tests (exe, zip bomb, macro, traversal, size) |
| 16 | Major frontend interactions work | **VERIFIED** for the tested journeys | 6 Playwright journeys + manual browser checks of every screen; not every control has an automated test |
| 17 | Responsive and keyboard accessible | **PARTIALLY VERIFIED** | mobile e2e (no overflow, skip link), keyboard slider/graph, axe on auth pages; a full manual screen-reader audit has **not** been done |
| 18 | Reduced-motion and non-3D fallbacks | **VERIFIED** | `useCan3D` tests; 2D radar/graph/constellation alternatives rendered in jsdom and in the browser |
| 19 | No secrets committed or exposed | **VERIFIED** | gitleaks clean on all to-be-committed files; `.env` git-ignored; CI generates its keys |
| 20 | DB isolation and migrations tested | **VERIFIED** | see 3 and 5 |
| 21 | Production config has no debug | **VERIFIED** | `debug=False` always; production validator fails closed; API docs off by default |
| 22 | Backup/restore documented and tested | **VERIFIED** (development environment) | `restore-check.sh` passed (36 tables identical); DR path with `grants.sql` verified on a scratch DB |
| 23 | Dependencies and versions pinned | **VERIFIED** | `uv.lock`, `package-lock.json`, digest-pinned images, exact model tags (`qwen3:8b` 500a1f067a9f Q4_K_M, `nomic-embed-text` 0a109f422b47) |
| 24 | Failures and limitations disclosed | this document | |

**Production readiness:** the system is **ready for a controlled, consented pilot on a trusted machine or private
network**. It is **NOT VERIFIED for public production**. That needs: a real TLS deployment and staging soak test, a
managed database with verified encryption at rest, a shared rate-limit store if more than one API process is run,
an independent security review or penetration test, and a readiness model trained on real, consented labels.

**Free hosting (Vercel + Render + Neon), added 2026-10-21:** the configuration was verified in a local
simulation, not on the real services. The same image ran with Render's limits (512 MB, 0.1 CPU) against a fresh
PostgreSQL 18 database set up like Neon (non-superuser owner role plus `infra/neon/setup.sql`); the automated
smoke journey passed. **NOT VERIFIED:** the real accounts, TLS and channel binding to Neon, cookie behaviour
through Vercel's forwarding, and the uptime pinger. See [free-hosting.md](operations/free-hosting.md).

## Known limitations and outstanding work

### Data and ML
* The active readiness model is trained on **synthetic data**. It must not inform real decisions. The UI labels
  it everywhere.
* Category features average self-reported and evidenced levels, so self-rating inflation affects inputs; the
  evidence-strength feature only partly offsets this.
* Subgroup gaps (TPR 0.18, ECE 0.11) on the synthetic test set show the reporting works; real fairness has not
  been assessed.
* The %→level mapping, trust weights, effort ranges and role weights are documented heuristics, not empirically
  calibrated.

### Mentor
* The RAG evaluation set is small and developer-written. The perfect retrieval score is optimistic until a
  held-out set exists.
* Residual minor inaccuracies remain in generated advice (for example, it once suggested a 1–10 rating scale).
  Numbers not in the context are flagged, and invented links are removed, but free-text errors are possible.
* One request at a time on an 8 GB GPU (bounded queue). Answers take about 5 s warm, plus 8–22 s if the model must
  load. No streaming cancellation inside Ollama beyond closing the connection.

### Security and operations
* In-process rate limiter: correct for one API process only.
* No breached-password corpus; TOTP codes are not replay-tracked within their 30-second window.
* Four Chroma HTTP-server CVEs have no fix yet. They are not reachable in the embedded mode used here
  ([exception record](security/dependency-exceptions.md)).
* Email delivery was verified only with the file backend; SMTP is implemented but untested here.
* OCR for scanned PDFs is not available; users are told so.
* The API image is 2.1 GB, of which about 345 MB is unused NVIDIA NCCL pulled in by XGBoost's Linux wheel.
  Switching to `xgboost-cpu` would slim it, but needs a lock change and re-test.
* The API cold start takes about 20 s because of heavy imports.

### Free hosting tiers
* No Personalized Mentor (Render has no GPU/Ollama) and no email (Render's free plan blocks SMTP). Users who forget
  their password cannot reset it.
* Uploaded files are lost when the Render container restarts or sleeps; the extracted analysis stays in the database.
* Cold start measured at 110–128 s at 0.1 CPU; Vercel gives up on forwarded requests after about 30 s, so an
  uptime pinger on `/api/v1/health/live` is required.
* Neon's free plan keeps only 6 hours of restore history; manual `pg_dump` backups are needed, and the restore path
  on Neon is not verified.
* The Render URL is public. Direct callers can spoof `X-Forwarded-For` and get around per-IP rate limits
  (per-account limits still apply).

### Product
* Assessments are recorded by mentors; there is no in-app test-taking engine.
* GitHub/portfolio links are stored, not verified automatically; verification is a mentor decision.
* Feedback is self-reported: ratings and comments are not a controlled evaluation. The admin list hides names and
  emails, but rows stay linked to accounts in the database, so they are deleted along with the account.
* The frontend has no light theme; the dark theme is the deliberate brand. Contrast has not been measured with
  tooling in a real browser (jsdom cannot).
