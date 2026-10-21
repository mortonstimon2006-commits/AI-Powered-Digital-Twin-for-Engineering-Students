# 01 — Complete file inventory

Every file tracked by git at commit `b2fae2a` (238 files), grouped by area. Facts in each entry were extracted
from the code by a parser (Python `ast`, TypeScript import/export patterns), not written from memory:

* **Lines** — physical line count. Binary files show `binary`.
* **Key symbols** — every top-level function, class and constant (Python) or export (TypeScript), with its line (`L42`).
* **Imports** — other repository files this file imports. Third-party packages are listed separately.
* **Imported by** — repository files that import this one (reverse dependencies).
* **Status** — Active / Active (entry point, test, migration, data, configuration) / Generated / Documentation,
  with the evidence for that label.

**Unused-code check:** every Python/TypeScript file that no other file imports is an entry point, configuration file,
migration, test, standalone script or package marker. No orphaned library module was found. Finer-grained dead code
found by reading: `catalogue_hint()` in `backend/app/services/rag/mentor.py` (never called), and seven API operations
with no user interface, listed in
[03-backend-code-walkthrough.md](03-backend-code-walkthrough.md#endpoints-without-a-user-interface).

Lockfiles and generated reports are inventoried but not reproduced.

## Root and repository configuration (9 files)

### `.dockerignore`

* **Purpose:** Excludes secrets, virtualenvs, node_modules, local data, model/dataset folders and docs from Docker build contexts; re-includes nothing else (the bundled model lives in `backend/artifacts/bundled/`).
* **Size:** 19 lines · **Status:** Active (configuration) — Read by the tool named in the purpose.

### `.editorconfig`

* **Purpose:** Editor defaults (UTF-8, LF, indentation) so files stay consistent across editors.
* **Size:** 15 lines · **Status:** Active (configuration) — Read by the tool named in the purpose.

### `.env.example`

* **Purpose:** Template of every environment variable with placeholders and generation instructions. The real `.env` is git-ignored and was not read for this audit.
* **Size:** 70 lines · **Status:** Active (configuration) — Read by the tool named in the purpose.

### `.gitattributes`

* **Purpose:** Normalises line endings to LF and marks binary types (png, joblib, pdf, docx, woff2).
* **Size:** 7 lines · **Status:** Active (configuration) — Read by the tool named in the purpose.

### `.github/workflows/ci.yml`

* **Purpose:** GitHub Actions pipeline: backend (ruff, mypy, migrations up/down/up + `alembic check`, pytest on real PostgreSQL, pip-audit), frontend (lint, typecheck, tests, build, npm audit), gitleaks secret scan, container build + Trivy scan.
* **Size:** 126 lines · **Status:** Active (configuration) — Read by the tool named in the purpose.

### `.gitignore`

* **Purpose:** Keeps `.env`, `backend/var/`, local model/dataset artifacts, backups, build output and dependencies out of git.
* **Size:** 41 lines · **Status:** Active (configuration) — Read by the tool named in the purpose.

### `README.md`

* **Purpose:** Project overview, feature map, setup commands, testing table, free-hosting summary and documentation index.
* **Size:** 171 lines · **Status:** Documentation — Not executed.

### `docker-compose.yml`

* **Purpose:** Local stack: `db` (PostgreSQL 18, loopback port 5433) always; `migrate`, `api` (internal port 8000) and `web` (127.0.0.1:8080) under the `app` profile, with hardened container options and host-gateway access to Ollama.
* **Size:** 99 lines · **Status:** Active (configuration) — Read by the tool named in the purpose.

### `render.yaml`

* **Purpose:** Render Blueprint for the free-tier API (Docker runtime, Singapore region, `sh /app/start-hosted.sh`, health check `/api/v1/health/live`, secrets entered in the dashboard).
* **Size:** 44 lines · **Status:** Active (configuration) — Read by the tool named in the purpose.

## Backend — configuration, packaging and migrations (8 files)

### `backend/Dockerfile`

* **Purpose:** Two-stage API image: uv installs the locked runtime dependencies (no dev/train groups), then a slim non-root runtime (uid 10001) with the app, migrations, knowledge base, bundled model and hosted start script.
* **Size:** 42 lines · **Status:** Active (configuration) — Read by the tool named in the purpose.

### `backend/alembic.ini`

* **Purpose:** Alembic configuration (script location `migrations`, OS path separator).
* **Size:** 38 lines · **Status:** Active (configuration) — Read by the tool named in the purpose.

### `backend/migrations/env.py`

* **Purpose:** Alembic environment: resolves the migration URL (test override, `ALEMBIC_DATABASE_URL`, or `MIGRATION_DATABASE_URL`) and runs migrations with the owner role.
* **Size:** 43 lines · **Status:** Active (entry point) — Loaded by Alembic.
* **Key symbols:** `_url()` L15, `run_migrations_offline()` L26, `run_migrations_online()` L32
* **Imports (repository):** `backend/app/config.py`, `backend/app/models/__init__.py`
* **Imports (third-party/stdlib):** `__future__`, `alembic`, `os`, `sqlalchemy`
* **Imported by:** —

### `backend/migrations/script.py.mako`

* **Purpose:** Template Alembic uses to generate new migration files.
* **Size:** 26 lines · **Status:** Active (configuration) — Read by the tool named in the purpose.

### `backend/migrations/versions/20261014_0001_initial_schema.py`

* **Purpose:** Migration 0001: creates all 35 application tables, constraints, indexes and UUIDv7 defaults.
* **Size:** 711 lines · **Status:** Active (migration) — Applied by Alembic; development database is at head `0002`.
* **Key symbols:** `upgrade()` L21, `downgrade()` L642
* **Imports (repository):** —
* **Imports (third-party/stdlib):** `__future__`, `alembic`, `collections`, `sqlalchemy`
* **Imported by:** —

### `backend/migrations/versions/20261014_0002_row_level_security.py`

* **Purpose:** Migration 0002: enables row-level security with owner policies on 20 student tables (+ documents read/write policies) and applies least-privilege grants (append-only audit table).
* **Size:** 82 lines · **Status:** Active (migration) — Applied by Alembic; development database is at head `0002`.
* **Key symbols:** `APP_ROLE` (const) L23, `OWNER_TABLES` (const) L25, `SUBJECT` (const) L32, `PRIVILEGED` (const) L33, `upgrade()` L36, `downgrade()` L76
* **Imports (repository):** —
* **Imports (third-party/stdlib):** `__future__`, `alembic`, `collections`
* **Imported by:** —

### `backend/pyproject.toml`

* **Purpose:** Backend package metadata, dependencies, dependency groups (`train`, `dev`), ruff/mypy/pytest configuration.
* **Size:** 91 lines · **Status:** Active (configuration) — Read by the tool named in the purpose.

### `backend/uv.lock`

* **Purpose:** Generated lockfile pinning every Python dependency version and hash (uv).
* **Size:** 2515 lines · **Status:** Generated — Produced by a tool or pipeline run; regenerate rather than edit by hand.

## Backend — application core (`backend/app/*.py`) (9 files)

### `backend/app/__init__.py`

* **Purpose:** Package marker for the FastAPI application.
* **Size:** 1 lines · **Status:** Active (package marker) — Makes the directory an importable Python package.
* **Key symbols:** —
* **Imports (repository):** —
* **Imports (third-party/stdlib):** —
* **Imported by:** —

### `backend/app/cli.py`

* **Purpose:** Operational CLI: seed, deploy-init, serve-hosted, validate-links, reindex-kb, create-admin, retention, models, bench-mentor.
* **Size:** 167 lines · **Status:** Active (entry point) — Entry point (`python -m app.cli …`).
* **Key symbols:** `cmd_seed()` L24, `cmd_deploy_init()` L32, `cmd_serve_hosted()` L44, `cmd_validate_links()` L71, `cmd_reindex_kb()` L85, `cmd_create_admin()` L93, `cmd_retention()` L120, `cmd_models()` L128, `cmd_bench_mentor()` L139, `main()` L145
* **Imports (repository):** `backend/app/db.py`, `backend/app/main.py`, `backend/app/ml/artifacts.py`, `backend/app/models/__init__.py`, `backend/app/security/passwords.py`, `backend/app/seed/catalogue.py`, `backend/app/services/audit.py`, `backend/app/services/auth_service.py`, `backend/app/services/link_checker.py`, `backend/app/services/privacy.py`, `backend/app/services/rag/benchmark.py`, `backend/app/services/rag/knowledge_base.py`
* **Imports (third-party/stdlib):** `__future__`, `alembic`, `argparse`, `collections`, `getpass`, `json`, `os`, `pathlib`, `sqlalchemy`, `sys`, `uvicorn`
* **Imported by:** —

### `backend/app/config.py`

* **Purpose:** Typed settings (pydantic-settings) for database, security, email, Ollama, storage and ML; fails closed on unsafe staging/production configuration; normalises hosted Postgres URLs to the psycopg driver.
* **Size:** 160 lines · **Status:** Active — Imported by 25 file(s).
* **Key symbols:** `BACKEND_DIR` (const) L17, `REPO_DIR` (const) L18, `Environment` (class) L21, `EmailBackend` (class) L28, `Settings` (class) L34, `get_settings()` L159
* **Imports (repository):** —
* **Imports (third-party/stdlib):** `__future__`, `enum`, `functools`, `pathlib`, `pydantic`, `pydantic_settings`
* **Imported by:** `backend/app/api/v1/admin.py`, `backend/app/api/v1/auth.py`, `backend/app/api/v1/documents.py`, `backend/app/api/v1/mentor.py`, `backend/app/api/v1/privacy.py`, `backend/app/db.py`, `backend/app/deps.py`, `backend/app/main.py`, `backend/app/middleware.py`, `backend/app/ml/artifacts.py`, `backend/app/ml/registry.py`, `backend/app/security/crypto.py`, `backend/app/security/tokens.py`, `backend/app/services/auth_service.py`, `backend/app/services/email.py`, `backend/app/services/privacy.py`, `backend/app/services/rag/benchmark.py`, `backend/app/services/rag/knowledge_base.py`, `backend/app/services/rag/mentor.py`, `backend/app/services/rag/ollama_client.py`, `backend/app/services/rag/store.py`, `backend/eval/run_rag_eval.py`, `backend/migrations/env.py`, `backend/tests/test_ml.py`, `backend/tests/test_rag.py`

### `backend/app/db.py`

* **Purpose:** SQLAlchemy engine/session factory, row-level-security scoping hook (`app.user_id`/`app.privileged` GUCs), `privileged_scope`, request and system sessions, optional NullPool.
* **Size:** 116 lines · **Status:** Active — Imported by 18 file(s).
* **Key symbols:** `_SET_SCOPE` (const) L27, `get_engine()` L31, `get_session_factory()` L48, `_apply_rls_scope()` L53, `set_rls_subject()` L61, `privileged_scope()` L70, `rowcount()` L85, `get_db()` L90, `system_session()` L104
* **Imports (repository):** `backend/app/config.py`
* **Imports (third-party/stdlib):** `__future__`, `collections`, `contextlib`, `functools`, `sqlalchemy`, `typing`, `uuid`
* **Imported by:** `backend/app/api/v1/admin.py`, `backend/app/api/v1/auth.py`, `backend/app/api/v1/health.py`, `backend/app/api/v1/mentor.py`, `backend/app/api/v1/staff.py`, `backend/app/cli.py`, `backend/app/deps.py`, `backend/app/ml/artifacts.py`, `backend/app/ml/registry.py`, `backend/app/services/audit.py`, `backend/app/services/auth_service.py`, `backend/app/services/privacy.py`, `backend/eval/run_rag_eval.py`, `backend/ml_pipeline/datasets.py`, `backend/tests/conftest.py`, `backend/tests/test_documents_privacy.py`, `backend/tests/test_ml.py`, `backend/tests/test_rag.py`

### `backend/app/deps.py`

* **Purpose:** FastAPI dependencies: cookie session loading, idle/absolute expiry, CSRF verification on unsafe methods, RLS subject binding, role guards and typed aliases (CurrentUser, AdminUser, StaffUser…).
* **Size:** 110 lines · **Status:** Active — Imported by 9 file(s).
* **Key symbols:** `LAST_SEEN_RESOLUTION` (const) L21, `Principal` (class) L25, `client_ip()` L38, `client_ip_prefix()` L46, `_load_session()` L50, `_verify_csrf()` L73, `get_principal()` L79, `get_optional_principal()` L90, `require_roles()` L97, `DB` (const) L108
* **Imports (repository):** `backend/app/config.py`, `backend/app/db.py`, `backend/app/errors.py`, `backend/app/middleware.py`, `backend/app/models/__init__.py`, `backend/app/security/tokens.py`
* **Imports (third-party/stdlib):** `__future__`, `dataclasses`, `datetime`, `fastapi`, `sqlalchemy`, `typing`, `uuid`
* **Imported by:** `backend/app/api/v1/admin.py`, `backend/app/api/v1/auth.py`, `backend/app/api/v1/career.py`, `backend/app/api/v1/documents.py`, `backend/app/api/v1/mentor.py`, `backend/app/api/v1/planning.py`, `backend/app/api/v1/privacy.py`, `backend/app/api/v1/staff.py`, `backend/app/api/v1/twin.py`

### `backend/app/errors.py`

* **Purpose:** Exception classes and handlers producing the uniform JSON error envelope; hides internal details (generic 500, 503 for database outages).
* **Size:** 117 lines · **Status:** Active — Imported by 14 file(s).
* **Key symbols:** `AppError` (class) L21, `NotFound` (class) L35, `Unauthorized` (class) L40, `Forbidden` (class) L45, `Conflict` (class) L50, `TooManyRequests` (class) L55, `ServiceUnavailable` (class) L64, `_envelope()` L69, `install_error_handlers()` L78
* **Imports (repository):** —
* **Imports (third-party/stdlib):** `__future__`, `fastapi`, `logging`, `sqlalchemy`, `starlette`, `typing`
* **Imported by:** `backend/app/api/v1/admin.py`, `backend/app/api/v1/career.py`, `backend/app/api/v1/documents.py`, `backend/app/api/v1/mentor.py`, `backend/app/api/v1/planning.py`, `backend/app/api/v1/privacy.py`, `backend/app/api/v1/staff.py`, `backend/app/api/v1/twin.py`, `backend/app/deps.py`, `backend/app/main.py`, `backend/app/security/ratelimit.py`, `backend/app/services/auth_service.py`, `backend/app/services/career/roadmap.py`, `backend/app/services/career/simulator.py`

### `backend/app/logging_config.py`

* **Purpose:** Structured JSON logging with redaction of sensitive keys and e-mail addresses; disables uvicorn's URL access log.
* **Size:** 67 lines · **Status:** Active — Imported by 2 file(s).
* **Key symbols:** `SENSITIVE_KEY` (const) L17, `EMAIL_RE` (const) L21, `redact()` L24, `JsonFormatter` (class) L36, `configure_logging()` L58
* **Imports (repository):** —
* **Imports (third-party/stdlib):** `__future__`, `datetime`, `json`, `logging`, `re`, `sys`, `typing`
* **Imported by:** `backend/app/main.py`, `backend/app/services/audit.py`

### `backend/app/main.py`

* **Purpose:** Application factory: logging, FastAPI instance (docs only outside production), error handlers, security + CORS middleware, `/api/v1` router; lifespan creates data folders and warms the model registry.
* **Size:** 63 lines · **Status:** Active (entry point) — ASGI entry point (`uvicorn app.main:app`).
* **Key symbols:** `lifespan()` L22, `create_app()` L35
* **Imports (repository):** `backend/app/api/v1/__init__.py`, `backend/app/config.py`, `backend/app/errors.py`, `backend/app/logging_config.py`, `backend/app/middleware.py`, `backend/app/ml/registry.py`
* **Imports (third-party/stdlib):** `__future__`, `collections`, `contextlib`, `fastapi`, `logging`
* **Imported by:** `backend/app/cli.py`, `backend/eval/run_rag_eval.py`, `backend/tests/conftest.py`

### `backend/app/middleware.py`

* **Purpose:** ASGI security middleware: request IDs and access log, Origin allow-list + `X-Requested-With` guard on unsafe `/api` calls, request body size limit, security headers, HSTS in production-like environments.
* **Size:** 144 lines · **Status:** Active — Imported by 2 file(s).
* **Key symbols:** `UNSAFE_METHODS` (const) L17, `_API_HEADERS` (const) L19, `_API_CSP` (const) L29, `_send_json_error()` L32, `SecurityMiddleware` (class) L52, `_BodyTooLarge` (class) L143
* **Imports (repository):** `backend/app/config.py`
* **Imports (third-party/stdlib):** `__future__`, `json`, `logging`, `starlette`, `time`, `uuid`
* **Imported by:** `backend/app/deps.py`, `backend/app/main.py`

## Backend — HTTP API (`backend/app/api`) (12 files)

### `backend/app/api/__init__.py`

* **Purpose:** Package marker.
* **Size:** 1 lines · **Status:** Active (package marker) — Makes the directory an importable Python package.
* **Key symbols:** —
* **Imports (repository):** —
* **Imports (third-party/stdlib):** —
* **Imported by:** —

### `backend/app/api/v1/__init__.py`

* **Purpose:** Builds `api_router` by including every v1 router module.
* **Size:** 7 lines · **Status:** Active — Makes the directory an importable Python package.
* **Key symbols:** —
* **Imports (repository):** `backend/app/api/v1/admin.py`, `backend/app/api/v1/auth.py`, `backend/app/api/v1/career.py`, `backend/app/api/v1/documents.py`, `backend/app/api/v1/health.py`, `backend/app/api/v1/mentor.py`, `backend/app/api/v1/planning.py`, `backend/app/api/v1/privacy.py`, `backend/app/api/v1/staff.py`, `backend/app/api/v1/twin.py`
* **Imports (third-party/stdlib):** `fastapi`
* **Imported by:** `backend/app/main.py`

### `backend/app/api/v1/admin.py`

* **Purpose:** Admin-only endpoints: system status, retention, audit log, feedback list/summary, users, mentor links, roles, skills, prerequisites, learning resources and link validation, model versions (activate/retire), knowledge base.
* **Size:** 639 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `system_status()` L55, `run_retention()` L85, `audit_log()` L94, `feedback_list()` L126, `feedback_summary()` L160, `list_users()` L175, `UserPatchIn` (class) L211, `patch_user()` L217, `MentorLinkIn` (class) L237, `list_links()` L243, `add_link()` L261, `remove_link()` L274, `RequirementIn` (class) L286, `RoleIn` (class) L296, `_apply_requirements()` L305, `create_role()` L316, `update_role()` L330, `deactivate_role()` L349, `SkillIn` (class) L359, `create_skill()` L371, `PrerequisitesIn` (class) L383, `set_prerequisites()` L390, `ResourceIn` (class) L411, `list_resources()` L426, `create_resource()` L452, `deactivate_resource()` L472, `ValidateIn` (class) L482, `validate_links()` L487, `list_models()` L498, `activate_model()` L520, `retire_model()` L540, `list_knowledge()` L555, `reindex()` L576, `upload_knowledge()` L592, `delete_knowledge()` L630
* **Imports (repository):** `backend/app/config.py`, `backend/app/db.py`, `backend/app/deps.py`, `backend/app/errors.py`, `backend/app/ml/registry.py`, `backend/app/models/__init__.py`, `backend/app/models/catalogue.py`, `backend/app/schemas/common.py`, `backend/app/services/audit.py`, `backend/app/services/auth_service.py`, `backend/app/services/catalogue.py`, `backend/app/services/documents/extract.py`, `backend/app/services/link_checker.py`, `backend/app/services/privacy.py`, `backend/app/services/rag/knowledge_base.py`, `backend/app/services/rag/mentor.py`, `backend/app/services/rag/ollama_client.py`, `backend/app/services/rag/store.py`, `backend/app/services/rag/text.py`
* **Imports (third-party/stdlib):** `__future__`, `datetime`, `fastapi`, `hashlib`, `networkx`, `pydantic`, `sqlalchemy`, `typing`, `uuid`
* **Imported by:** `backend/app/api/v1/__init__.py`

### `backend/app/api/v1/auth.py`

* **Purpose:** Authentication endpoints: register, login (+MFA), logout, me, CSRF refresh, sessions, password change/forgot/reset, email verification, MFA setup/verify/disable; sets hardened cookies.
* **Size:** 261 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `REGISTER_MESSAGE` (const) L33, `RESET_MESSAGE` (const) L36, `_set_auth_cookies()` L39, `_clear_auth_cookies()` L57, `user_out()` L63, `_me()` L75, `register()` L89, `login()` L108, `login_mfa()` L125, `logout()` L140, `me()` L147, `refresh_csrf()` L152, `sessions()` L169, `revoke_session()` L185, `revoke_other_sessions()` L191, `change_password()` L198, `forgot_password()` L214, `reset_password()` L224, `verify_email()` L233, `resend_verification()` L239, `mfa_setup()` L247, `mfa_verify()` L253, `mfa_disable()` L259
* **Imports (repository):** `backend/app/config.py`, `backend/app/db.py`, `backend/app/deps.py`, `backend/app/models/__init__.py`, `backend/app/schemas/auth.py`, `backend/app/schemas/common.py`, `backend/app/services/auth_service.py`, `backend/app/services/email.py`
* **Imports (third-party/stdlib):** `__future__`, `fastapi`, `sqlalchemy`, `uuid`
* **Imported by:** `backend/app/api/v1/__init__.py`

### `backend/app/api/v1/career.py`

* **Purpose:** Role catalogue, readiness (model info, analyse, latest, history), skill gaps (per role, summary, sensitivity), simulations and saved scenarios, current feature vector.
* **Size:** 375 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `_role_summary()` L32, `list_roles()` L60, `get_role()` L71, `list_catalogue_skills()` L80, `readiness_model_info()` L102, `run_readiness()` L145, `_strip()` L161, `latest_readiness()` L166, `readiness_history()` L192, `_config()` L212, `role_gap_analysis()` L222, `role_matches()` L264, `role_ranking_sensitivity()` L288, `run_simulation()` L303, `SaveScenarioIn` (class) L308, `save_scenario()` L314, `list_scenarios()` L337, `delete_scenario()` L349, `current_features()` L359
* **Imports (repository):** `backend/app/deps.py`, `backend/app/errors.py`, `backend/app/ml/feature_schema.py`, `backend/app/ml/registry.py`, `backend/app/models/__init__.py`, `backend/app/schemas/common.py`, `backend/app/security/ratelimit.py`, `backend/app/seed/catalogue_data.py`, `backend/app/services/audit.py`, `backend/app/services/career/gap_engine.py`, `backend/app/services/career/readiness.py`, `backend/app/services/career/simulator.py`, `backend/app/services/catalogue.py`, `backend/app/services/twin/features.py`, `backend/app/services/twin/history.py`
* **Imports (third-party/stdlib):** `__future__`, `fastapi`, `pydantic`, `sqlalchemy`, `typing`, `uuid`
* **Imported by:** `backend/app/api/v1/__init__.py`

### `backend/app/api/v1/documents.py`

* **Purpose:** Resume/JD upload and analysis, pasted job descriptions, download, deletion, confirming extracted skills, resume-vs-JD comparison; private RAG indexing.
* **Size:** 310 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `MAX_DOCS_PER_USER` (const) L36, `_doc_out()` L39, `_owned()` L58, `_safe_name()` L65, `_index_private()` L72, `list_documents()` L89, `upload_document()` L95, `JobTextIn` (class) L152, `paste_job_description()` L158, `get_document()` L182, `download_document()` L187, `delete_doc()` L206, `ConfirmSkill` (class) L223, `ConfirmSkillsIn` (class) L228, `confirm_skills()` L233, `CompareIn` (class) L253, `compare()` L259
* **Imports (repository):** `backend/app/config.py`, `backend/app/deps.py`, `backend/app/errors.py`, `backend/app/models/__init__.py`, `backend/app/schemas/common.py`, `backend/app/security/ratelimit.py`, `backend/app/services/audit.py`, `backend/app/services/career/gap_engine.py`, `backend/app/services/catalogue.py`, `backend/app/services/documents/extract.py`, `backend/app/services/documents/parse.py`, `backend/app/services/rag/ollama_client.py`, `backend/app/services/rag/store.py`, `backend/app/services/rag/text.py`, `backend/app/services/twin/history.py`
* **Imports (third-party/stdlib):** `__future__`, `datetime`, `fastapi`, `hashlib`, `logging`, `pydantic`, `sqlalchemy`, `typing`, `uuid`
* **Imported by:** `backend/app/api/v1/__init__.py`

### `backend/app/api/v1/health.py`

* **Purpose:** Liveness (`/health/live`, no dependencies) and readiness (`/health/ready`: database, model, mentor LLM) probes.
* **Size:** 35 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `live()` L13, `ready()` L18
* **Imports (repository):** `backend/app/db.py`, `backend/app/ml/registry.py`, `backend/app/services/rag/ollama_client.py`
* **Imports (third-party/stdlib):** `__future__`, `fastapi`, `sqlalchemy`
* **Imported by:** `backend/app/api/v1/__init__.py`

### `backend/app/api/v1/mentor.py`

* **Purpose:** Personalized Mentor endpoints: status, conversations CRUD, and `/mentor/ask` with Server-Sent-Events streaming, link sanitisation, unverified-number flags and persistence.
* **Size:** 292 lines · **Status:** Active — Imported by 2 file(s).
* **Key symbols:** `UNAVAILABLE_TEXT` (const) L29, `AskIn` (class) L35, `mentor_status()` L41, `list_conversations()` L53, `_owned_conversation()` L63, `get_conversation()` L73, `delete_conversation()` L99, `_sse()` L105, `_save_assistant()` L109, `_sanitize()` L147, `ask()` L159
* **Imports (repository):** `backend/app/config.py`, `backend/app/db.py`, `backend/app/deps.py`, `backend/app/errors.py`, `backend/app/models/__init__.py`, `backend/app/schemas/common.py`, `backend/app/security/ratelimit.py`, `backend/app/services/catalogue.py`, `backend/app/services/rag/mentor.py`, `backend/app/services/rag/ollama_client.py`
* **Imports (third-party/stdlib):** `__future__`, `collections`, `fastapi`, `json`, `logging`, `pydantic`, `sqlalchemy`, `starlette`, `typing`, `uuid`
* **Imported by:** `backend/app/api/v1/__init__.py`, `backend/tests/test_rag.py`

### `backend/app/api/v1/planning.py`

* **Purpose:** Knowledge graph and insights, roadmap generation/listing/compare/item updates/reorder, progress timeline.
* **Size:** 251 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `knowledge_graph()` L35, `graph_insights()` L53, `GenerateRoadmapIn` (class) L80, `generate()` L86, `get_active()` L99, `list_roadmaps()` L107, `get_roadmap()` L127, `compare()` L132, `ItemUpdateIn` (class) L138, `_owned_item()` L143, `update_item()` L151, `ReorderIn` (class) L182, `reorder()` L187, `progress_timeline()` L216
* **Imports (repository):** `backend/app/deps.py`, `backend/app/errors.py`, `backend/app/models/__init__.py`, `backend/app/schemas/common.py`, `backend/app/security/ratelimit.py`, `backend/app/services/audit.py`, `backend/app/services/career/gap_engine.py`, `backend/app/services/career/knowledge_graph.py`, `backend/app/services/career/roadmap.py`, `backend/app/services/twin/history.py`
* **Imports (third-party/stdlib):** `__future__`, `datetime`, `fastapi`, `pydantic`, `sqlalchemy`, `typing`, `uuid`
* **Imported by:** `backend/app/api/v1/__init__.py`

### `backend/app/api/v1/privacy.py`

* **Purpose:** Consents, privacy policy, data export, hard account deletion, user feedback (rate-limited).
* **Size:** 145 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `get_consents()` L26, `ConsentIn` (class) L30, `put_consent()` L35, `policy()` L49, `export()` L74, `DeleteAccountIn` (class) L86, `delete_account()` L92, `FeedbackIn` (class) L111, `feedback()` L121, `my_feedback()` L129
* **Imports (repository):** `backend/app/config.py`, `backend/app/deps.py`, `backend/app/errors.py`, `backend/app/models/__init__.py`, `backend/app/schemas/common.py`, `backend/app/security/passwords.py`, `backend/app/security/ratelimit.py`, `backend/app/security/tokens.py`, `backend/app/services/audit.py`, `backend/app/services/privacy.py`, `backend/app/services/rag/ollama_client.py`, `backend/app/services/twin/history.py`
* **Imports (third-party/stdlib):** `__future__`, `contextlib`, `fastapi`, `json`, `pydantic`, `sqlalchemy`, `typing`
* **Imported by:** `backend/app/api/v1/__init__.py`

### `backend/app/api/v1/staff.py`

* **Purpose:** Mentor/admin tools gated by mentor link AND student consent: student list/overview, recording verified assessments, verifying evidence, assessor readiness labels, verification queue.
* **Size:** 288 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `_accessible_student()` L44, `list_students()` L60, `student_overview()` L87, `state_projects()` L136, `RecordAssessmentIn` (class) L140, `record_assessment()` L155, `VerifyIn` (class) L189, `verify_item()` L196, `LabelIn` (class) L220, `record_label()` L236, `verification_queue()` L261, `assessment_catalogue()` L282
* **Imports (repository):** `backend/app/db.py`, `backend/app/deps.py`, `backend/app/errors.py`, `backend/app/models/__init__.py`, `backend/app/schemas/common.py`, `backend/app/services/audit.py`, `backend/app/services/career/gap_engine.py`, `backend/app/services/twin/history.py`
* **Imports (third-party/stdlib):** `__future__`, `datetime`, `fastapi`, `pydantic`, `sqlalchemy`, `typing`, `uuid`
* **Imported by:** `backend/app/api/v1/__init__.py`

### `backend/app/api/v1/twin.py`

* **Purpose:** Digital-twin CRUD: profile, role preferences, onboarding, skill ratings, projects/experiences/certifications with skill evidence, assessments, verification requests, snapshots, diffs, completeness.
* **Size:** 561 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `_profile()` L57, `_has_consent()` L66, `_profile_out()` L71, `_commit_change()` L97, `get_profile()` L106, `update_profile()` L111, `patch_profile()` L127, `update_role_preferences()` L144, `complete_onboarding()` L162, `list_skills()` L175, `_scale()` L200, `_check_skill_ids()` L206, `rate_skill()` L214, `rate_skills_bulk()` L227, `clear_skill_rating()` L244, `_replace_evidence()` L255, `_evidence_for()` L280, `_owned()` L295, `list_projects()` L306, `create_project()` L313, `update_project()` L326, `delete_project()` L341, `list_experiences()` L351, `create_experience()` L358, `update_experience()` L370, `delete_experience()` L386, `list_certifications()` L396, `create_certification()` L405, `delete_certification()` L417, `_assessment_out()` L426, `list_assessment_results()` L443, `add_self_reported_assessment()` L466, `delete_self_reported_assessment()` L489, `request_verification()` L499, `list_snapshots()` L516, `diff_snapshots()` L537, `get_completeness()` L559
* **Imports (repository):** `backend/app/deps.py`, `backend/app/errors.py`, `backend/app/models/__init__.py`, `backend/app/schemas/common.py`, `backend/app/schemas/twin.py`, `backend/app/seed/catalogue_data.py`, `backend/app/services/audit.py`, `backend/app/services/catalogue.py`, `backend/app/services/twin/history.py`
* **Imports (third-party/stdlib):** `__future__`, `datetime`, `fastapi`, `sqlalchemy`, `typing`, `uuid`
* **Imported by:** `backend/app/api/v1/__init__.py`

## Backend — schemas and security (9 files)

### `backend/app/schemas/__init__.py`

* **Purpose:** Package marker.
* **Size:** 1 lines · **Status:** Active (package marker) — Makes the directory an importable Python package.
* **Key symbols:** —
* **Imports (repository):** —
* **Imports (third-party/stdlib):** —
* **Imported by:** —

### `backend/app/schemas/auth.py`

* **Purpose:** Pydantic request/response models for authentication (strict: unknown fields rejected).
* **Size:** 100 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `RegisterIn` (class) L12, `LoginIn` (class) L28, `MfaLoginIn` (class) L33, `TokenIn` (class) L38, `ForgotPasswordIn` (class) L42, `ResetPasswordIn` (class) L46, `ChangePasswordIn` (class) L51, `MfaVerifyIn` (class) L56, `MfaDisableIn` (class) L60, `UserOut` (class) L65, `MeOut` (class) L75, `LoginOut` (class) L82, `SessionOut` (class) L88, `MfaSetupOut` (class) L98
* **Imports (repository):** `backend/app/schemas/common.py`
* **Imports (third-party/stdlib):** `__future__`, `datetime`, `pydantic`, `typing`, `uuid`
* **Imported by:** `backend/app/api/v1/auth.py`

### `backend/app/schemas/common.py`

* **Purpose:** `StrictModel` (extra=forbid), `ApiModel`, `Message` and pagination schemas shared by all routers.
* **Size:** 31 lines · **Status:** Active — Imported by 12 file(s).
* **Key symbols:** `StrictModel` (class) L6, `ApiModel` (class) L12, `Message` (class) L18, `Page` (class) L22, `PageParams` (class) L29
* **Imports (repository):** —
* **Imports (third-party/stdlib):** `__future__`, `pydantic`
* **Imported by:** `backend/app/api/v1/admin.py`, `backend/app/api/v1/auth.py`, `backend/app/api/v1/career.py`, `backend/app/api/v1/documents.py`, `backend/app/api/v1/mentor.py`, `backend/app/api/v1/planning.py`, `backend/app/api/v1/privacy.py`, `backend/app/api/v1/staff.py`, `backend/app/api/v1/twin.py`, `backend/app/schemas/auth.py`, `backend/app/schemas/twin.py`, `backend/app/services/career/simulator.py`

### `backend/app/schemas/twin.py`

* **Purpose:** Validated twin payloads: profile, ratings, projects/experience/certifications with https-only URLs, evidence links, assessments and their response models.
* **Size:** 251 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `_URL_RE` (const) L12, `LEARNING_PREFS` (const) L13, `_https_url()` L17, `_clean_list()` L25, `ProfileIn` (class) L34, `RolePreferencesIn` (class) L60, `ProfileOut` (class) L71, `SkillRatingIn` (class) L90, `BulkSkillRating` (class) L94, `BulkSkillRatingsIn` (class) L99, `EvidenceLinkIn` (class) L104, `ProjectIn` (class) L110, `ExperienceIn` (class) L141, `CertificationIn` (class) L160, `SelfReportedAssessmentIn` (class) L174, `EvidenceOut` (class) L188, `ProjectOut` (class) L195, `ExperienceOut` (class) L211, `CertificationOut` (class) L224, `AssessmentResultOut` (class) L235, `VerificationRequestIn` (class) L249
* **Imports (repository):** `backend/app/schemas/common.py`
* **Imports (third-party/stdlib):** `__future__`, `datetime`, `pydantic`, `re`, `typing`, `uuid`
* **Imported by:** `backend/app/api/v1/twin.py`

### `backend/app/security/__init__.py`

* **Purpose:** Package marker.
* **Size:** 1 lines · **Status:** Active (package marker) — Makes the directory an importable Python package.
* **Key symbols:** —
* **Imports (repository):** —
* **Imports (third-party/stdlib):** —
* **Imported by:** —

### `backend/app/security/crypto.py`

* **Purpose:** Fernet field encryption for TOTP secrets with a key held outside the database.
* **Size:** 27 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `_fernet()` L15, `encrypt()` L19, `decrypt()` L23
* **Imports (repository):** `backend/app/config.py`
* **Imports (third-party/stdlib):** `__future__`, `cryptography`, `functools`
* **Imported by:** `backend/app/services/auth_service.py`

### `backend/app/security/passwords.py`

* **Purpose:** Argon2id hashing (t=3, m=64 MiB, p=2), timing-equalising dummy hash, password policy checks.
* **Size:** 79 lines · **Status:** Active — Imported by 3 file(s).
* **Key symbols:** `_DUMMY_HASH` (const) L15, `MIN_LENGTH` (const) L17, `MAX_LENGTH` (const) L18, `_COMMON` (const) L22, `hash_password()` L46, `verify_password()` L50, `needs_rehash()` L57, `password_problems()` L61
* **Imports (repository):** —
* **Imports (third-party/stdlib):** `__future__`, `argon2`
* **Imported by:** `backend/app/api/v1/privacy.py`, `backend/app/cli.py`, `backend/app/services/auth_service.py`

### `backend/app/security/ratelimit.py`

* **Purpose:** In-process sliding-window rate limiter with HMAC-pseudonymised keys and the named limits (login, register, reset, mentor, upload, simulation, feedback…).
* **Size:** 71 lines · **Status:** Active — Imported by 7 file(s).
* **Key symbols:** `Limit` (class) L21, `SlidingWindowLimiter` (class) L27, `LOGIN_IP` (const) L61, `LOGIN_ACCOUNT` (const) L62, `REGISTER_IP` (const) L63, `RESET_REQUEST_IP` (const) L64, `RESET_REQUEST_ACCOUNT` (const) L65, `TOKEN_REDEEM_IP` (const) L66, `MENTOR_USER` (const) L67, `UPLOAD_USER` (const) L68, `SIMULATION_USER` (const) L69, `EXPENSIVE_USER` (const) L70, `FEEDBACK_USER` (const) L71
* **Imports (repository):** `backend/app/errors.py`, `backend/app/security/tokens.py`
* **Imports (third-party/stdlib):** `__future__`, `collections`, `dataclasses`, `threading`, `time`
* **Imported by:** `backend/app/api/v1/career.py`, `backend/app/api/v1/documents.py`, `backend/app/api/v1/mentor.py`, `backend/app/api/v1/planning.py`, `backend/app/api/v1/privacy.py`, `backend/app/services/auth_service.py`, `backend/tests/conftest.py`

### `backend/app/security/tokens.py`

* **Purpose:** Random tokens, SHA-256 digests, HMAC keyed digests, constant-time comparison, IP prefix minimisation (/24, /48).
* **Size:** 41 lines · **Status:** Active — Imported by 4 file(s).
* **Key symbols:** `new_token()` L13, `digest()` L17, `keyed_digest()` L22, `constant_time_equals()` L28, `ip_prefix()` L32
* **Imports (repository):** `backend/app/config.py`
* **Imports (third-party/stdlib):** `__future__`, `hashlib`, `hmac`, `ipaddress`, `secrets`
* **Imported by:** `backend/app/api/v1/privacy.py`, `backend/app/deps.py`, `backend/app/security/ratelimit.py`, `backend/app/services/auth_service.py`

## Backend — database models (6 files)

### `backend/app/models/__init__.py`

* **Purpose:** Re-exports every ORM model (single import point for services, migrations and tests).
* **Size:** 101 lines · **Status:** Active — Makes the directory an importable Python package.
* **Key symbols:** —
* **Imports (repository):** `backend/app/models/base.py`, `backend/app/models/catalogue.py`, `backend/app/models/identity.py`, `backend/app/models/intelligence.py`, `backend/app/models/twin.py`
* **Imports (third-party/stdlib):** —
* **Imported by:** `backend/app/api/v1/admin.py`, `backend/app/api/v1/auth.py`, `backend/app/api/v1/career.py`, `backend/app/api/v1/documents.py`, `backend/app/api/v1/mentor.py`, `backend/app/api/v1/planning.py`, `backend/app/api/v1/privacy.py`, `backend/app/api/v1/staff.py`, `backend/app/api/v1/twin.py`, `backend/app/cli.py`, `backend/app/deps.py`, `backend/app/ml/artifacts.py`, `backend/app/ml/registry.py`, `backend/app/seed/catalogue.py`, `backend/app/services/audit.py`, `backend/app/services/auth_service.py`, `backend/app/services/career/readiness.py`, `backend/app/services/career/roadmap.py`, `backend/app/services/catalogue.py`, `backend/app/services/link_checker.py`, `backend/app/services/privacy.py`, `backend/app/services/rag/knowledge_base.py`, `backend/app/services/rag/mentor.py`, `backend/app/services/twin/history.py`, `backend/app/services/twin/state.py`, `backend/eval/run_rag_eval.py`, `backend/migrations/env.py`, `backend/ml_pipeline/datasets.py`, `backend/tests/test_ml.py`, `backend/tests/test_rag.py`

### `backend/app/models/base.py`

* **Purpose:** Declarative base with a naming convention, UUIDv7 primary-key helper and timestamp column helpers.
* **Size:** 33 lines · **Status:** Active — Imported by 5 file(s).
* **Key symbols:** `NAMING_CONVENTION` (const) L10, `Base` (class) L19, `uuid_pk()` L23, `created_at_col()` L28, `updated_at_col()` L32
* **Imports (repository):** —
* **Imports (third-party/stdlib):** `__future__`, `datetime`, `sqlalchemy`, `uuid`
* **Imported by:** `backend/app/models/__init__.py`, `backend/app/models/catalogue.py`, `backend/app/models/identity.py`, `backend/app/models/intelligence.py`, `backend/app/models/twin.py`

### `backend/app/models/catalogue.py`

* **Purpose:** Reference-data models: Skill, SkillPrerequisite, CareerRole, RoleSkillRequirement, RoleVersion, LearningResource, ResourceSkill, Assessment, AssessmentSkill.
* **Size:** 191 lines · **Status:** Active — Imported by 2 file(s).
* **Key symbols:** `SKILL_CATEGORIES` (const) L28, `Skill` (class) L41, `SkillPrerequisite` (class) L65, `CareerRole` (class) L78, `RoleSkillRequirement` (class) L98, `RoleVersion` (class) L120, `LearningResource` (class) L135, `ResourceSkill` (class) L164, `Assessment` (class) L171, `AssessmentSkill` (class) L187
* **Imports (repository):** `backend/app/models/base.py`
* **Imports (third-party/stdlib):** `__future__`, `datetime`, `sqlalchemy`, `typing`, `uuid`
* **Imported by:** `backend/app/api/v1/admin.py`, `backend/app/models/__init__.py`

### `backend/app/models/identity.py`

* **Purpose:** User, UserSession (hash-only tokens), AuthToken, Consent, MentorLink, AuditEvent.
* **Size:** 146 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `USER_ROLES` (const) L26, `User` (class) L29, `UserSession` (class) L55, `AuthToken` (class) L74, `CONSENT_PURPOSES` (const) L94, `Consent` (class) L97, `MentorLink` (class) L113, `AuditEvent` (class) L128
* **Imports (repository):** `backend/app/models/base.py`
* **Imports (third-party/stdlib):** `__future__`, `datetime`, `sqlalchemy`, `typing`, `uuid`
* **Imported by:** `backend/app/models/__init__.py`

### `backend/app/models/intelligence.py`

* **Purpose:** ModelVersion, Prediction, WhatIfScenario, Roadmap, RoadmapItem, RoadmapEvent, Document, MentorConversation, MentorMessage, UserFeedback.
* **Size:** 258 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `_user_fk()` L30, `ModelVersion` (class) L37, `Prediction` (class) L63, `WhatIfScenario` (class) L80, `Roadmap` (class) L96, `RoadmapItem` (class) L117, `RoadmapEvent` (class) L152, `Document` (class) L169, `MentorConversation` (class) L205, `MentorMessage` (class) L215, `UserFeedback` (class) L241
* **Imports (repository):** `backend/app/models/base.py`
* **Imports (third-party/stdlib):** `__future__`, `datetime`, `sqlalchemy`, `typing`, `uuid`
* **Imported by:** `backend/app/models/__init__.py`

### `backend/app/models/twin.py`

* **Purpose:** StudentProfile, StudentRolePreference, StudentSkill, Project, Experience, Certification, AssessmentResult, SkillEvidence, TwinSnapshot, ReadinessLabel.
* **Size:** 249 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `VERIFICATION_CHECK` (const) L29, `_user_fk()` L32, `StudentProfile` (class) L36, `StudentRolePreference` (class) L66, `StudentSkill` (class) L75, `Project` (class) L93, `Experience` (class) L121, `Certification` (class) L145, `AssessmentResult` (class) L165, `SkillEvidence` (class) L187, `TwinSnapshot` (class) L216, `ReadinessLabel` (class) L233
* **Imports (repository):** `backend/app/models/base.py`
* **Imports (third-party/stdlib):** `__future__`, `datetime`, `sqlalchemy`, `typing`, `uuid`
* **Imported by:** `backend/app/models/__init__.py`

## Backend — machine learning (runtime) (5 files)

### `backend/app/ml/__init__.py`

* **Purpose:** Package marker.
* **Size:** 1 lines · **Status:** Active (package marker) — Makes the directory an importable Python package.
* **Key symbols:** —
* **Imports (repository):** —
* **Imports (third-party/stdlib):** —
* **Imported by:** —

### `backend/app/ml/artifacts.py`

* **Purpose:** Registers model artifacts in `model_versions` (idempotent) and registers/activates the artifacts shipped in the image at start-up (`register_bundled`).
* **Size:** 100 lines · **Status:** Active — Imported by 3 file(s).
* **Key symbols:** `register_artifact()` L23, `register_bundled()` L69
* **Imports (repository):** `backend/app/config.py`, `backend/app/db.py`, `backend/app/ml/feature_schema.py`, `backend/app/ml/registry.py`, `backend/app/models/__init__.py`
* **Imports (third-party/stdlib):** `__future__`, `datetime`, `json`, `pathlib`, `sqlalchemy`
* **Imported by:** `backend/app/cli.py`, `backend/ml_pipeline/train.py`, `backend/tests/test_ml.py`

### `backend/app/ml/explain.py`

* **Purpose:** SHAP explainers (Linear for logistic regression, Tree otherwise), aggregation of missing-indicator columns, global importance and single-prediction explanations.
* **Size:** 121 lines · **Status:** Active — Imported by 2 file(s).
* **Key symbols:** `MISSING_PREFIX` (const) L24, `output_space()` L27, `make_explainer()` L31, `_class1()` L37, `shap_matrix()` L41, `aggregate_to_features()` L51, `global_importance()` L62, `_fmt_value()` L79, `explain_single()` L94
* **Imports (repository):** `backend/app/ml/feature_schema.py`
* **Imports (third-party/stdlib):** `__future__`, `math`, `numpy`, `pandas`, `shap`, `sklearn`, `typing`
* **Imported by:** `backend/app/services/career/readiness.py`, `backend/ml_pipeline/train.py`

### `backend/app/ml/feature_schema.py`

* **Purpose:** The single 19-feature contract (names, ranges, units), target definition, schema hash and vector validation.
* **Size:** 118 lines · **Status:** Active — Imported by 12 file(s).
* **Key symbols:** `CATEGORY_FEATURES` (const) L14, `CATEGORY_LABELS` (const) L15, `FeatureSpec` (class) L29, `TARGET_NAME` (const) L91, `TARGET_DEFINITION` (const) L92, `schema_hash()` L99, `validate_vector()` L104
* **Imports (repository):** —
* **Imports (third-party/stdlib):** `__future__`, `dataclasses`, `hashlib`, `json`
* **Imported by:** `backend/app/api/v1/career.py`, `backend/app/ml/artifacts.py`, `backend/app/ml/explain.py`, `backend/app/ml/registry.py`, `backend/app/services/career/readiness.py`, `backend/app/services/career/simulator.py`, `backend/app/services/twin/features.py`, `backend/ml_pipeline/datasets.py`, `backend/ml_pipeline/synthetic.py`, `backend/ml_pipeline/train.py`, `backend/tests/test_career.py`, `backend/tests/test_ml.py`

### `backend/app/ml/registry.py`

* **Purpose:** Model registry: verifies artifact path, SHA-256, schema hash and library versions before loading; exposes the active model or an explicit unavailable status.
* **Size:** 140 lines · **Status:** Active — Imported by 8 file(s).
* **Key symbols:** `sha256_file()` L32, `_major_minor()` L40, `LoadedModel` (class) L45, `ModelRegistry` (class) L65
* **Imports (repository):** `backend/app/config.py`, `backend/app/db.py`, `backend/app/ml/feature_schema.py`, `backend/app/models/__init__.py`
* **Imports (third-party/stdlib):** `__future__`, `dataclasses`, `hashlib`, `joblib`, `json`, `logging`, `pathlib`, `sklearn`, `sqlalchemy`, `threading`, `typing`, `xgboost`
* **Imported by:** `backend/app/api/v1/admin.py`, `backend/app/api/v1/career.py`, `backend/app/api/v1/health.py`, `backend/app/main.py`, `backend/app/ml/artifacts.py`, `backend/app/services/career/readiness.py`, `backend/tests/conftest.py`, `backend/tests/test_ml.py`

## Backend — reference data seeding (3 files)

### `backend/app/seed/__init__.py`

* **Purpose:** Package marker.
* **Size:** 1 lines · **Status:** Active (package marker) — Makes the directory an importable Python package.
* **Key symbols:** —
* **Imports (repository):** —
* **Imports (third-party/stdlib):** —
* **Imported by:** —

### `backend/app/seed/catalogue.py`

* **Purpose:** Idempotent catalogue loader (inserts missing records, never overwrites admin edits) with static-data validation.
* **Size:** 130 lines · **Status:** Active — Imported by 3 file(s).
* **Key symbols:** `_validate_static_data()` L24, `seed_catalogue()` L41
* **Imports (repository):** `backend/app/models/__init__.py`, `backend/app/seed/catalogue_data.py`, `backend/app/services/catalogue.py`
* **Imports (third-party/stdlib):** `__future__`, `networkx`, `sqlalchemy`
* **Imported by:** `backend/app/cli.py`, `backend/eval/run_rag_eval.py`, `backend/tests/conftest.py`

### `backend/app/seed/catalogue_data.py`

* **Purpose:** Authored reference data: 42 skills with aliases, 33 prerequisite edges, 6 roles with 91 requirements, 7 assessments, 50 learning resources, proficiency level definitions.
* **Size:** 1396 lines · **Status:** Active — Imported by 3 file(s).
* **Key symbols:** `FRAMEWORK_VERSION` (const) L22, `FRAMEWORK_SOURCE_NOTE` (const) L23, `PROFICIENCY_LEVELS` (const) L29
* **Imports (repository):** —
* **Imports (third-party/stdlib):** `__future__`
* **Imported by:** `backend/app/api/v1/career.py`, `backend/app/api/v1/twin.py`, `backend/app/seed/catalogue.py`

## Backend — services (28 files)

### `backend/app/services/__init__.py`

* **Purpose:** Package marker.
* **Size:** 1 lines · **Status:** Active (package marker) — Makes the directory an importable Python package.
* **Key symbols:** —
* **Imports (repository):** —
* **Imports (third-party/stdlib):** —
* **Imported by:** —

### `backend/app/services/audit.py`

* **Purpose:** Writes redacted audit events in the current transaction (`record`) or in an independent transaction (`record_standalone`, for failures that roll back).
* **Size:** 57 lines · **Status:** Active — Imported by 9 file(s).
* **Key symbols:** `record()` L18, `record_standalone()` L44
* **Imports (repository):** `backend/app/db.py`, `backend/app/logging_config.py`, `backend/app/models/__init__.py`
* **Imports (third-party/stdlib):** `__future__`, `logging`, `sqlalchemy`, `typing`, `uuid`
* **Imported by:** `backend/app/api/v1/admin.py`, `backend/app/api/v1/career.py`, `backend/app/api/v1/documents.py`, `backend/app/api/v1/planning.py`, `backend/app/api/v1/privacy.py`, `backend/app/api/v1/staff.py`, `backend/app/api/v1/twin.py`, `backend/app/cli.py`, `backend/app/services/auth_service.py`

### `backend/app/services/auth_service.py`

* **Purpose:** Registration, email verification, login with lockout and rehash, sessions, password change/reset, TOTP MFA.
* **Size:** 378 lines · **Status:** Active — Imported by 4 file(s).
* **Key symbols:** `POLICY_VERSION` (const) L36, `GENERIC_LOGIN_ERROR` (const) L37, `LOCKOUT_THRESHOLD` (const) L38, `VERIFY_TTL` (const) L39, `RESET_TTL` (const) L40, `MFA_CHALLENGE_TTL` (const) L41, `MFA_ISSUER` (const) L42, `_now()` L45, `_require_strong()` L49, `_issue_token()` L55, `_redeem_token()` L61, `RegistrationOutcome` (class) L72, `register()` L80, `verify_email()` L111, `new_verification_token()` L124, `IssuedSession` (class) L141, `create_session()` L147, `rotate_csrf()` L163, `LoginResult` (class) L171, `login()` L177, `login_mfa()` L232, `logout()` L254, `list_sessions()` L260, `revoke_session()` L270, `revoke_all_sessions()` L279, `change_password()` L290, `request_password_reset()` L306, `reset_password()` L326, `mfa_begin_setup()` L347, `mfa_confirm()` L357, `mfa_disable()` L368
* **Imports (repository):** `backend/app/config.py`, `backend/app/db.py`, `backend/app/errors.py`, `backend/app/models/__init__.py`, `backend/app/security/crypto.py`, `backend/app/security/passwords.py`, `backend/app/security/ratelimit.py`, `backend/app/security/tokens.py`, `backend/app/services/audit.py`
* **Imports (third-party/stdlib):** `__future__`, `dataclasses`, `datetime`, `pyotp`, `sqlalchemy`, `uuid`
* **Imported by:** `backend/app/api/v1/admin.py`, `backend/app/api/v1/auth.py`, `backend/app/cli.py`, `backend/app/services/privacy.py`

### `backend/app/services/career/__init__.py`

* **Purpose:** Package marker.
* **Size:** 1 lines · **Status:** Active (package marker) — Makes the directory an importable Python package.
* **Key symbols:** —
* **Imports (repository):** —
* **Imports (third-party/stdlib):** —
* **Imported by:** —

### `backend/app/services/career/gap_engine.py`

* **Purpose:** Role matching and skill-gap analysis: weighted coverage, match bounds, priorities with unlock/blocking bonuses, actions, Monte-Carlo ranking sensitivity.
* **Size:** 391 lines · **Status:** Active — Imported by 9 file(s).
* **Key symbols:** `GapConfig` (class) L38, `DEFAULT_CONFIG` (const) L56, `SkillGap` (class) L60, `RoleMatch` (class) L89, `_prereq_graph()` L110, `_descendants()` L118, `_slots()` L126, `_coverage()` L140, `_evidence_met()` L146, `analyse_role()` L158, `_action_text()` L285, `analyse_all_roles()` L304, `ranking_sensitivity()` L319
* **Imports (repository):** `backend/app/services/catalogue.py`, `backend/app/services/twin/proficiency.py`
* **Imports (third-party/stdlib):** `__future__`, `dataclasses`, `networkx`, `random`, `typing`
* **Imported by:** `backend/app/api/v1/career.py`, `backend/app/api/v1/documents.py`, `backend/app/api/v1/planning.py`, `backend/app/api/v1/staff.py`, `backend/app/services/career/knowledge_graph.py`, `backend/app/services/career/roadmap.py`, `backend/app/services/career/simulator.py`, `backend/app/services/rag/mentor.py`, `backend/tests/test_career.py`

### `backend/app/services/career/knowledge_graph.py`

* **Purpose:** NetworkX knowledge graph (global + per-student overlay with provenance), insight queries, 3D layout payload.
* **Size:** 338 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `skill_node()` L32, `global_graph()` L36, `student_graph()` L94, `blocking_prerequisites()` L135, `resources_for_top_gaps()` L170, `alternative_roles()` L198, `multi_role_unlocks()` L225, `visual_payload()` L248
* **Imports (repository):** `backend/app/services/career/gap_engine.py`, `backend/app/services/catalogue.py`, `backend/app/services/twin/proficiency.py`, `backend/app/services/twin/state.py`
* **Imports (third-party/stdlib):** `__future__`, `networkx`, `threading`, `typing`
* **Imported by:** `backend/app/api/v1/planning.py`

### `backend/app/services/career/readiness.py`

* **Purpose:** Readiness inference: calibrated probability, band, SHAP explanation, warnings (synthetic, low information, out-of-distribution), deterministic summary, prediction storage.
* **Size:** 191 lines · **Status:** Active — Imported by 4 file(s).
* **Key symbols:** `BAND_LABELS` (const) L25, `LOW_INFORMATION_SHARE` (const) L31, `_explainer()` L34, `_band()` L41, `_ood_warnings()` L48, `predict()` L69, `summarise()` L141, `store_prediction()` L162, `prediction_history()` L184, `finite()` L190
* **Imports (repository):** `backend/app/ml/explain.py`, `backend/app/ml/feature_schema.py`, `backend/app/ml/registry.py`, `backend/app/models/__init__.py`, `backend/app/services/twin/features.py`
* **Imports (third-party/stdlib):** `__future__`, `math`, `numpy`, `pandas`, `sqlalchemy`, `typing`, `uuid`
* **Imported by:** `backend/app/api/v1/career.py`, `backend/app/services/career/simulator.py`, `backend/tests/test_career.py`, `backend/tests/test_ml.py`

### `backend/app/services/career/roadmap.py`

* **Purpose:** Deterministic roadmap generation (prerequisite expansion, priority-aware topological sort, effort heuristics, scheduling), progress carry-over, staleness, comparison.
* **Size:** 393 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `GENERATOR_VERSION` (const) L34, `LEVEL_HOURS` (const) L36, `ASSESS_HOURS` (const) L37, `VERIFY_HOURS` (const) L38, `MAX_ITEMS` (const) L39, `_effort()` L42, `_pick_resource()` L59, `_reason()` L76, `plan_items()` L95, `_active()` L223, `generate_roadmap()` L227, `roadmap_view()` L281, `compare_roadmaps()` L363, `owned_roadmap()` L385, `active_or_none()` L392
* **Imports (repository):** `backend/app/errors.py`, `backend/app/models/__init__.py`, `backend/app/services/career/gap_engine.py`, `backend/app/services/catalogue.py`, `backend/app/services/twin/proficiency.py`, `backend/app/services/twin/state.py`
* **Imports (third-party/stdlib):** `__future__`, `datetime`, `math`, `networkx`, `sqlalchemy`, `typing`, `uuid`
* **Imported by:** `backend/app/api/v1/planning.py`

### `backend/app/services/career/simulator.py`

* **Purpose:** What-if simulator: validated scenario schema, deep-copy of the twin, same estimation/feature/model/gap pipeline, baseline vs hypothetical output.
* **Size:** 281 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `KIND_TO_ASSESSMENT_KIND` (const) L37, `SkillChange` (class) L40, `AssessmentChange` (class) L46, `ScenarioChanges` (class) L51, `SimulationRequest` (class) L76, `apply_changes()` L81, `_readiness()` L177, `simulate()` L198
* **Imports (repository):** `backend/app/errors.py`, `backend/app/ml/feature_schema.py`, `backend/app/schemas/common.py`, `backend/app/services/career/gap_engine.py`, `backend/app/services/career/readiness.py`, `backend/app/services/catalogue.py`, `backend/app/services/twin/features.py`, `backend/app/services/twin/proficiency.py`, `backend/app/services/twin/state.py`
* **Imports (third-party/stdlib):** `__future__`, `pydantic`, `sqlalchemy`, `typing`, `uuid`
* **Imported by:** `backend/app/api/v1/career.py`

### `backend/app/services/catalogue.py`

* **Purpose:** Loads the reference catalogue into frozen dataclasses with a process cache keyed by a database fingerprint.
* **Size:** 218 lines · **Status:** Active — Imported by 17 file(s).
* **Key symbols:** `SkillInfo` (class) L29, `Requirement` (class) L42, `RoleInfo` (class) L53, `ResourceInfo` (class) L65, `Catalogue` (class) L81, `_fingerprint()` L98, `load_catalogue()` L114, `role_spec()` L194, `snapshot_role_version()` L217
* **Imports (repository):** `backend/app/models/__init__.py`
* **Imports (third-party/stdlib):** `__future__`, `dataclasses`, `sqlalchemy`, `threading`, `typing`, `uuid`
* **Imported by:** `backend/app/api/v1/admin.py`, `backend/app/api/v1/career.py`, `backend/app/api/v1/documents.py`, `backend/app/api/v1/mentor.py`, `backend/app/api/v1/twin.py`, `backend/app/seed/catalogue.py`, `backend/app/services/career/gap_engine.py`, `backend/app/services/career/knowledge_graph.py`, `backend/app/services/career/roadmap.py`, `backend/app/services/career/simulator.py`, `backend/app/services/documents/parse.py`, `backend/app/services/rag/knowledge_base.py`, `backend/app/services/rag/mentor.py`, `backend/app/services/twin/features.py`, `backend/app/services/twin/history.py`, `backend/app/services/twin/proficiency.py`, `backend/tests/test_career.py`

### `backend/app/services/documents/__init__.py`

* **Purpose:** Package marker.
* **Size:** 1 lines · **Status:** Active (package marker) — Makes the directory an importable Python package.
* **Key symbols:** —
* **Imports (repository):** —
* **Imports (third-party/stdlib):** —
* **Imported by:** —

### `backend/app/services/documents/extract.py`

* **Purpose:** Safe text extraction: content sniffing, DOCX zip-bomb/macro checks, PDF/DOCX parsing in a separate process with a timeout and caps.
* **Size:** 150 lines · **Status:** Active — Imported by 2 file(s).
* **Key symbols:** `MAX_PDF_PAGES` (const) L21, `MAX_TEXT_CHARS` (const) L22, `DOCX_MAX_ENTRIES` (const) L23, `DOCX_MAX_UNCOMPRESSED` (const) L24, `DOCX_MAX_RATIO` (const) L25, `EXTRACT_TIMEOUT_S` (const) L26, `RejectedFile` (class) L29, `Extracted` (class) L34, `sniff()` L42, `_check_docx()` L65, `_parse_worker()` L80, `_child()` L115, `extract()` L124
* **Imports (repository):** —
* **Imports (third-party/stdlib):** `__future__`, `dataclasses`, `docx`, `io`, `multiprocessing`, `pypdf`, `zipfile`
* **Imported by:** `backend/app/api/v1/admin.py`, `backend/app/api/v1/documents.py`

### `backend/app/services/documents/parse.py`

* **Purpose:** Deterministic resume and job-description analysis: section splitting, catalogue alias matching, writing suggestions, JD skill weighting.
* **Size:** 215 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `SECTION_PATTERNS` (const) L17, `_SECTION_RES` (const) L28, `WEAK_STARTS` (const) L29, `ACTION_VERBS` (const) L30, `URL_RE` (const) L49, `_alias_patterns()` L53, `_patterns()` L63, `split_sections()` L71, `find_skills()` L92, `resume_suggestions()` L122, `analyse_resume()` L178, `analyse_job_description()` L194
* **Imports (repository):** `backend/app/services/catalogue.py`
* **Imports (third-party/stdlib):** `__future__`, `collections`, `functools`, `re`, `typing`
* **Imported by:** `backend/app/api/v1/documents.py`

### `backend/app/services/email.py`

* **Purpose:** Transactional e-mail via file outbox (development), SMTP with STARTTLS, or disabled.
* **Size:** 84 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `email_enabled()` L17, `send_email()` L21, `verification_email()` L48, `account_exists_email()` L58, `password_reset_email()` L67, `password_changed_email()` L78
* **Imports (repository):** `backend/app/config.py`
* **Imports (third-party/stdlib):** `__future__`, `datetime`, `email`, `logging`, `smtplib`, `ssl`
* **Imported by:** `backend/app/api/v1/auth.py`

### `backend/app/services/link_checker.py`

* **Purpose:** SSRF-guarded HTTPS link validation for learning resources (public IPs only, redirects re-checked).
* **Size:** 100 lines · **Status:** Active — Imported by 2 file(s).
* **Key symbols:** `USER_AGENT` (const) L23, `MAX_REDIRECTS` (const) L24, `UnsafeUrl` (class) L27, `assert_public_https()` L31, `CheckResult` (class) L48, `check_url()` L55, `validate_resources()` L78
* **Imports (repository):** `backend/app/models/__init__.py`
* **Imports (third-party/stdlib):** `__future__`, `dataclasses`, `datetime`, `httpx`, `ipaddress`, `socket`, `sqlalchemy`, `urllib`
* **Imported by:** `backend/app/api/v1/admin.py`, `backend/app/cli.py`

### `backend/app/services/privacy.py`

* **Purpose:** Consent definitions, data export, hard account deletion (vectors + files + rows), retention job.
* **Size:** 200 lines · **Status:** Active — Imported by 4 file(s).
* **Key symbols:** `CONSENT_INFO` (const) L47, `consents()` L58, `set_consent()` L73, `_rows()` L85, `export_user_data()` L98, `_remove_user_files()` L145, `delete_account()` L152, `apply_retention()` L168
* **Imports (repository):** `backend/app/config.py`, `backend/app/db.py`, `backend/app/models/__init__.py`, `backend/app/services/auth_service.py`, `backend/app/services/rag/store.py`
* **Imports (third-party/stdlib):** `__future__`, `datetime`, `logging`, `shutil`, `sqlalchemy`, `typing`, `uuid`
* **Imported by:** `backend/app/api/v1/admin.py`, `backend/app/api/v1/privacy.py`, `backend/app/cli.py`, `backend/tests/test_documents_privacy.py`

### `backend/app/services/rag/__init__.py`

* **Purpose:** Package marker.
* **Size:** 1 lines · **Status:** Active (package marker) — Makes the directory an importable Python package.
* **Key symbols:** —
* **Imports (repository):** —
* **Imports (third-party/stdlib):** —
* **Imported by:** —

### `backend/app/services/rag/benchmark.py`

* **Purpose:** Local-inference benchmark (cold/warm latency, tokens/s, VRAM) used by `app.cli bench-mentor`.
* **Size:** 123 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `BENCH_CONTEXT` (const) L18, `_nvidia_smi()` L24, `_one()` L44, `run_benchmark()` L75
* **Imports (repository):** `backend/app/config.py`, `backend/app/services/rag/mentor.py`
* **Imports (third-party/stdlib):** `__future__`, `asyncio`, `httpx`, `shutil`, `statistics`, `subprocess`, `time`, `typing`
* **Imported by:** `backend/app/cli.py`

### `backend/app/services/rag/knowledge_base.py`

* **Purpose:** Indexes `knowledge/*.md` and role guides generated from the catalogue into the global vector collection.
* **Size:** 112 lines · **Status:** Active — Imported by 4 file(s).
* **Key symbols:** `KNOWLEDGE_DIR` (const) L20, `LEVEL_NAMES` (const) L21, `_title()` L24, `role_guides()` L31, `reindex_global()` L75, `knowledge_files()` L111
* **Imports (repository):** `backend/app/config.py`, `backend/app/models/__init__.py`, `backend/app/services/catalogue.py`, `backend/app/services/rag/store.py`, `backend/app/services/rag/text.py`
* **Imports (third-party/stdlib):** `__future__`, `hashlib`, `pathlib`, `re`, `sqlalchemy`, `typing`
* **Imported by:** `backend/app/api/v1/admin.py`, `backend/app/cli.py`, `backend/eval/run_rag_eval.py`, `backend/tests/test_rag.py`

### `backend/app/services/rag/mentor.py`

* **Purpose:** Mentor orchestration: system prompt, deterministic student context, retrieval packing within token budgets, link sanitiser, unverified-number check, concurrency gate.
* **Size:** 371 lines · **Status:** Active — Imported by 4 file(s).
* **Key symbols:** `CHARS_PER_TOKEN` (const) L34, `SYSTEM_BUDGET_TOKENS` (const) L35, `CONTEXT_BUDGET_TOKENS` (const) L36, `RETRIEVAL_BUDGET_TOKENS` (const) L37, `HISTORY_BUDGET_TOKENS` (const) L38, `ANSWER_TOKENS` (const) L39, `SYSTEM_PROMPT` (const) L41, `INTENTS` (const) L54, `approx_tokens()` L61, `truncate_to_tokens()` L65, `MentorContext` (class) L74, `_fmt_level()` L83, `build_student_context()` L87, `_numbers()` L205, `_MD_LINK` (const) L209, `_BARE_URL` (const) L210, `_norm_url()` L213, `sanitize_links()` L217, `unverified_numbers()` L242, `assemble()` L252, `build_messages()` L283, `prompt_tokens_estimate()` L292, `MentorBusy` (class) L299, `GenerationGate` (class) L303, `gate()` L345, `sources_payload()` L352, `now_ms()` L366, `catalogue_hint()` L370
* **Imports (repository):** `backend/app/config.py`, `backend/app/models/__init__.py`, `backend/app/services/career/gap_engine.py`, `backend/app/services/catalogue.py`, `backend/app/services/rag/store.py`, `backend/app/services/rag/text.py`, `backend/app/services/twin/history.py`
* **Imports (third-party/stdlib):** `__future__`, `asyncio`, `dataclasses`, `re`, `sqlalchemy`, `time`, `typing`, `uuid`
* **Imported by:** `backend/app/api/v1/admin.py`, `backend/app/api/v1/mentor.py`, `backend/app/services/rag/benchmark.py`, `backend/tests/test_rag.py`

### `backend/app/services/rag/ollama_client.py`

* **Purpose:** HTTP client for the local Ollama API: status, embeddings (`/api/embed`) and streamed chat (`/api/chat`, thinking off).
* **Size:** 146 lines · **Status:** Active — Imported by 6 file(s).
* **Key symbols:** `_STATUS_TTL` (const) L22, `OllamaUnavailable` (class) L27, `_model_present()` L31, `fetch_status()` L37, `ollama_status_cached()` L71, `invalidate_status()` L79, `embed()` L84, `chat_stream()` L103
* **Imports (repository):** `backend/app/config.py`
* **Imports (third-party/stdlib):** `__future__`, `collections`, `httpx`, `json`, `logging`, `threading`, `time`, `typing`
* **Imported by:** `backend/app/api/v1/admin.py`, `backend/app/api/v1/documents.py`, `backend/app/api/v1/health.py`, `backend/app/api/v1/mentor.py`, `backend/app/api/v1/privacy.py`, `backend/app/services/rag/store.py`

### `backend/app/services/rag/store.py`

* **Purpose:** Chroma persistent collections (cosine), chunk indexing with contextual headers, owner-scoped retrieval with injection-flag filtering.
* **Size:** 166 lines · **Status:** Active — Imported by 7 file(s).
* **Key symbols:** `EMBED_BATCH` (const) L27, `DOC_PREFIX` (const) L28, `QUERY_PREFIX` (const) L29, `_client()` L33, `_collection()` L39, `IndexResult` (class) L49, `index_chunks()` L54, `delete_document()` L97, `delete_owner()` L102, `Passage` (class) L107, `retrieve()` L118, `stats()` L162
* **Imports (repository):** `backend/app/config.py`, `backend/app/services/rag/ollama_client.py`, `backend/app/services/rag/text.py`
* **Imports (third-party/stdlib):** `__future__`, `chromadb`, `dataclasses`, `functools`, `logging`, `threading`, `typing`, `uuid`
* **Imported by:** `backend/app/api/v1/admin.py`, `backend/app/api/v1/documents.py`, `backend/app/services/privacy.py`, `backend/app/services/rag/knowledge_base.py`, `backend/app/services/rag/mentor.py`, `backend/eval/run_rag_eval.py`, `backend/tests/test_rag.py`

### `backend/app/services/rag/text.py`

* **Purpose:** Heading-aware chunking, PII redaction, control-token stripping and prompt-injection pattern detection.
* **Size:** 89 lines · **Status:** Active — Imported by 6 file(s).
* **Key symbols:** `EMAIL_RE` (const) L8, `PHONE_RE` (const) L9, `CONTROL_TOKENS` (const) L10, `INJECTION_PATTERNS` (const) L12, `redact_pii()` L30, `strip_control_tokens()` L35, `injection_hits()` L39, `Chunk` (class) L44, `chunk_text()` L50
* **Imports (repository):** —
* **Imports (third-party/stdlib):** `__future__`, `dataclasses`, `re`
* **Imported by:** `backend/app/api/v1/admin.py`, `backend/app/api/v1/documents.py`, `backend/app/services/rag/knowledge_base.py`, `backend/app/services/rag/mentor.py`, `backend/app/services/rag/store.py`, `backend/tests/test_rag.py`

### `backend/app/services/twin/__init__.py`

* **Purpose:** Package marker.
* **Size:** 1 lines · **Status:** Active (package marker) — Makes the directory an importable Python package.
* **Key symbols:** —
* **Imports (repository):** —
* **Imports (third-party/stdlib):** —
* **Imported by:** —

### `backend/app/services/twin/features.py`

* **Purpose:** Converts a twin into the 19-feature ML vector (unknown stays None) and computes the known-input share.
* **Size:** 59 lines · **Status:** Active — Imported by 4 file(s).
* **Key symbols:** `STRONG` (const) L13, `_latest_verified_pct()` L16, `build_features()` L24, `known_share()` L57
* **Imports (repository):** `backend/app/ml/feature_schema.py`, `backend/app/services/catalogue.py`, `backend/app/services/twin/proficiency.py`, `backend/app/services/twin/state.py`
* **Imports (third-party/stdlib):** `__future__`, `math`
* **Imported by:** `backend/app/api/v1/career.py`, `backend/app/services/career/readiness.py`, `backend/app/services/career/simulator.py`, `backend/app/services/twin/history.py`

### `backend/app/services/twin/history.py`

* **Purpose:** Content-addressed snapshots, profile completeness score, human-readable diffs, feature deltas.
* **Size:** 182 lines · **Status:** Active — Imported by 7 file(s).
* **Key symbols:** `ensure_snapshot()` L18, `latest_snapshot()` L43, `SECTIONS` (const) L49, `completeness()` L59, `diff_states()` L115, `feature_deltas()` L170, `estimates_for()` L179
* **Imports (repository):** `backend/app/models/__init__.py`, `backend/app/services/catalogue.py`, `backend/app/services/twin/features.py`, `backend/app/services/twin/proficiency.py`, `backend/app/services/twin/state.py`
* **Imports (third-party/stdlib):** `__future__`, `sqlalchemy`, `typing`, `uuid`
* **Imported by:** `backend/app/api/v1/career.py`, `backend/app/api/v1/documents.py`, `backend/app/api/v1/planning.py`, `backend/app/api/v1/privacy.py`, `backend/app/api/v1/staff.py`, `backend/app/api/v1/twin.py`, `backend/app/services/rag/mentor.py`

### `backend/app/services/twin/proficiency.py`

* **Purpose:** Evidence-aware proficiency estimation with trust levels (assessed > verified evidence > unverified evidence > self-reported > unknown).
* **Size:** 133 lines · **Status:** Active — Imported by 7 file(s).
* **Key symbols:** `TRUST` (const) L24, `STATUS_ORDER` (const) L31, `pct_to_level()` L34, `SkillEstimate` (class) L41, `estimate_skills()` L54
* **Imports (repository):** `backend/app/services/catalogue.py`, `backend/app/services/twin/state.py`
* **Imports (third-party/stdlib):** `__future__`, `dataclasses`, `typing`
* **Imported by:** `backend/app/services/career/gap_engine.py`, `backend/app/services/career/knowledge_graph.py`, `backend/app/services/career/roadmap.py`, `backend/app/services/career/simulator.py`, `backend/app/services/twin/features.py`, `backend/app/services/twin/history.py`, `backend/tests/test_career.py`

### `backend/app/services/twin/state.py`

* **Purpose:** `TwinState` plain-data snapshot of a student, its deep `clone`, JSON round-trip, content hash, and the database loader.
* **Size:** 210 lines · **Status:** Active — Imported by 6 file(s).
* **Key symbols:** `EvidenceItem` (class) L36, `AssessmentItem` (class) L47, `ProjectItem` (class) L58, `ExperienceItem` (class) L67, `CertificationItem` (class) L78, `TwinState` (class) L87, `_months_between()` L127, `load_twin_state()` L133
* **Imports (repository):** `backend/app/models/__init__.py`
* **Imports (third-party/stdlib):** `__future__`, `copy`, `dataclasses`, `datetime`, `hashlib`, `json`, `sqlalchemy`, `typing`, `uuid`
* **Imported by:** `backend/app/services/career/knowledge_graph.py`, `backend/app/services/career/roadmap.py`, `backend/app/services/career/simulator.py`, `backend/app/services/twin/features.py`, `backend/app/services/twin/history.py`, `backend/app/services/twin/proficiency.py`

## Backend — ML training pipeline (6 files)

### `backend/ml_pipeline/__init__.py`

* **Purpose:** Package marker.
* **Size:** 1 lines · **Status:** Active (package marker) — Makes the directory an importable Python package.
* **Key symbols:** —
* **Imports (repository):** —
* **Imports (third-party/stdlib):** —
* **Imported by:** —

### `backend/ml_pipeline/datasets.py`

* **Purpose:** Dataset sources (synthetic, provenance-checked CSV, consented in-app labels), schema/quality validation and protected-column refusal.
* **Size:** 171 lines · **Status:** Active — Imported by 2 file(s).
* **Key symbols:** `REQUIRED_PROVENANCE_KEYS` (const) L27, `GROUP_COL` (const) L28, `LABEL_COL` (const) L29, `Dataset` (class) L33, `validate_and_clean()` L45, `load_dataset()` L105, `_load_app_labels()` L138
* **Imports (repository):** `backend/app/db.py`, `backend/app/ml/feature_schema.py`, `backend/app/models/__init__.py`, `backend/ml_pipeline/synthetic.py`
* **Imports (third-party/stdlib):** `__future__`, `dataclasses`, `hashlib`, `json`, `numpy`, `pandas`, `pathlib`, `sqlalchemy`, `typing`
* **Imported by:** `backend/ml_pipeline/train.py`, `backend/tests/test_ml.py`

### `backend/ml_pipeline/evaluation.py`

* **Purpose:** Metrics: ROC/PR-AUC, Brier, log loss, ECE, reliability, point metrics, student-clustered bootstrap CIs, band analysis, subgroup report.
* **Size:** 160 lines · **Status:** Active — Imported by 2 file(s).
* **Key symbols:** `BANDS` (const) L22, `band_for()` L25, `expected_calibration_error()` L32, `reliability_table()` L43, `point_metrics()` L62, `ranking_metrics()` L76, `grouped_bootstrap_ci()` L87, `band_analysis()` L113, `subgroup_report()` L129
* **Imports (repository):** —
* **Imports (third-party/stdlib):** `__future__`, `numpy`, `pandas`, `sklearn`, `typing`
* **Imported by:** `backend/ml_pipeline/train.py`, `backend/tests/test_ml.py`

### `backend/ml_pipeline/report.py`

* **Purpose:** Renders `report.md` for an artifact strictly from its manifest.
* **Size:** 128 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `_f()` L10, `write_report()` L14
* **Imports (repository):** —
* **Imports (third-party/stdlib):** `__future__`, `pathlib`, `typing`
* **Imported by:** `backend/ml_pipeline/train.py`

### `backend/ml_pipeline/synthetic.py`

* **Purpose:** Documented synthetic cohort generator `synthetic-cohort-v1` (latent aptitude/diligence/communication → noisy features → assessor-style label).
* **Size:** 103 lines · **Status:** Active — Imported by 2 file(s).
* **Key symbols:** `GENERATOR_VERSION` (const) L30, `FOCUS_CATEGORIES` (const) L32, `_sigmoid()` L40, `generate_cohort()` L44
* **Imports (repository):** `backend/app/ml/feature_schema.py`
* **Imports (third-party/stdlib):** `__future__`, `numpy`, `pandas`
* **Imported by:** `backend/ml_pipeline/datasets.py`, `backend/tests/test_ml.py`

### `backend/ml_pipeline/train.py`

* **Purpose:** End-to-end training: grouped split, leakage checks, grid search of three candidates with grouped CV, Occam selection, Platt calibration, threshold, test evaluation, SHAP, packaging, manifest.
* **Size:** 529 lines · **Status:** Active (entry point) — Entry point (`python -m ml_pipeline.train`).
* **Key symbols:** `BACKEND` (const) L59, `SIMPLICITY` (const) L60, `ECE_TOLERANCE` (const) L61, `N_JOBS` (const) L63, `candidates()` L66, `grouped_split()` L106, `_split_summary()` L118, `leakage_checks()` L127, `select_model()` L160, `tune()` L173, `f1_threshold()` L204, `make_figures()` L210, `train()` L283, `register()` L503, `main()` L509
* **Imports (repository):** `backend/app/ml/artifacts.py`, `backend/app/ml/explain.py`, `backend/app/ml/feature_schema.py`, `backend/ml_pipeline/datasets.py`, `backend/ml_pipeline/evaluation.py`, `backend/ml_pipeline/report.py`
* **Imports (third-party/stdlib):** `__future__`, `argparse`, `dataclasses`, `datetime`, `hashlib`, `joblib`, `json`, `matplotlib`, `numpy`, `pandas`, `pathlib`, `platform`, `shap`, `sklearn`, `sys`, `time`, `typing`, `xgboost`
* **Imported by:** `backend/tests/conftest.py`, `backend/tests/test_ml.py`

## Backend — model artifacts (11 files)

### `backend/artifacts/bundled/readiness-202610141151-synth-logistic-d41952/figures/calibration.png`

* **Purpose:** Generated evaluation figure (calibration) for the bundled model (synthetic test set).
* **Size:** binary · **Status:** Generated — Produced by a tool or pipeline run; regenerate rather than edit by hand.

### `backend/artifacts/bundled/readiness-202610141151-synth-logistic-d41952/figures/confusion.png`

* **Purpose:** Generated evaluation figure (confusion) for the bundled model (synthetic test set).
* **Size:** binary · **Status:** Generated — Produced by a tool or pipeline run; regenerate rather than edit by hand.

### `backend/artifacts/bundled/readiness-202610141151-synth-logistic-d41952/figures/model_comparison.png`

* **Purpose:** Generated evaluation figure (model comparison) for the bundled model (synthetic test set).
* **Size:** binary · **Status:** Generated — Produced by a tool or pipeline run; regenerate rather than edit by hand.

### `backend/artifacts/bundled/readiness-202610141151-synth-logistic-d41952/figures/pr.png`

* **Purpose:** Generated evaluation figure (pr) for the bundled model (synthetic test set).
* **Size:** binary · **Status:** Generated — Produced by a tool or pipeline run; regenerate rather than edit by hand.

### `backend/artifacts/bundled/readiness-202610141151-synth-logistic-d41952/figures/roc.png`

* **Purpose:** Generated evaluation figure (roc) for the bundled model (synthetic test set).
* **Size:** binary · **Status:** Generated — Produced by a tool or pipeline run; regenerate rather than edit by hand.

### `backend/artifacts/bundled/readiness-202610141151-synth-logistic-d41952/figures/shap_global.png`

* **Purpose:** Generated evaluation figure (shap global) for the bundled model (synthetic test set).
* **Size:** binary · **Status:** Generated — Produced by a tool or pipeline run; regenerate rather than edit by hand.

### `backend/artifacts/bundled/readiness-202610141151-synth-logistic-d41952/manifest.json`

* **Purpose:** Generated by `ml_pipeline.train`: full training manifest (data, selection, calibration, metrics, CIs, fairness, leakage checks, ranges, libraries, checksum).
* **Size:** 1065 lines · **Status:** Generated — Produced by a tool or pipeline run; regenerate rather than edit by hand.

### `backend/artifacts/bundled/readiness-202610141151-synth-logistic-d41952/model.joblib`

* **Purpose:** Generated model bundle (imputer+scaler+logistic regression pipeline, Platt-calibrated wrapper, SHAP background). Loaded only after SHA-256 verification.
* **Size:** binary · **Status:** Generated — Produced by a tool or pipeline run; regenerate rather than edit by hand.

### `backend/artifacts/bundled/readiness-202610141151-synth-logistic-d41952/report.md`

* **Purpose:** Generated human-readable evaluation report for the bundled model.
* **Size:** 141 lines · **Status:** Generated — Produced by a tool or pipeline run; regenerate rather than edit by hand.

### `backend/artifacts/datasets/.gitkeep`

* **Purpose:** Keeps the (git-ignored) dataset output folder in the repository.
* **Size:** 1 lines · **Status:** Active (configuration) — Read by the tool named in the purpose.

### `backend/artifacts/models/.gitkeep`

* **Purpose:** Keeps the (git-ignored) local model artifact folder in the repository.
* **Size:** 1 lines · **Status:** Active (configuration) — Read by the tool named in the purpose.

## Backend — RAG evaluation (3 files)

### `backend/eval/__init__.py`

* **Purpose:** Package marker.
* **Size:** 1 lines · **Status:** Active (package marker) — Makes the directory an importable Python package.
* **Key symbols:** —
* **Imports (repository):** —
* **Imports (third-party/stdlib):** —
* **Imported by:** —

### `backend/eval/rag_eval_set.json`

* **Purpose:** Developer-written RAG evaluation set v2: 24 retrieval questions with expected source documents and 9 generation scenarios with pass rules.
* **Size:** 301 lines · **Status:** Active (configuration) — Read by the tool named in the purpose.

### `backend/eval/run_rag_eval.py`

* **Purpose:** Runs the RAG evaluation against the real local models on the test database and writes `docs/reports/rag-eval.{json,md}`.
* **Size:** 340 lines · **Status:** Active (entry point) — Entry point (`python -m eval.run_rag_eval`).
* **Key symbols:** `REPO` (const) L26, `BACKEND` (const) L27, `_require_env()` L31, `PASSWORD` (const) L63, `INJECTED_RESUME` (const) L64, `_reset_db()` L74, `_client()` L81, `_signup()` L87, `_ask()` L100, `_score()` L129, `main()` L154, `render()` L281
* **Imports (repository):** `backend/app/config.py`, `backend/app/db.py`, `backend/app/main.py`, `backend/app/models/__init__.py`, `backend/app/seed/catalogue.py`, `backend/app/services/rag/knowledge_base.py`, `backend/app/services/rag/store.py`
* **Imports (third-party/stdlib):** `__future__`, `alembic`, `datetime`, `dotenv`, `fastapi`, `json`, `os`, `pathlib`, `re`, `sqlalchemy`, `statistics`, `sys`, `tempfile`, `time`, `uuid`
* **Imported by:** —

## Backend — scripts (2 files)

### `backend/scripts/smoke_hosted.py`

* **Purpose:** Post-deployment smoke test: throwaway account walks the core journey and is deleted.
* **Size:** 110 lines · **Status:** Active (entry point) — Standalone script.
* **Key symbols:** `Client` (class) L22, `main()` L57
* **Imports (repository):** —
* **Imports (third-party/stdlib):** `__future__`, `httpx`, `secrets`, `sys`, `time`, `typing`
* **Imported by:** —

### `backend/scripts/start-hosted.sh`

* **Purpose:** Container start command for single-container hosts: `python -m app.cli serve-hosted`.
* **Size:** 6 lines · **Status:** Active (entry point) — Container command on Render (`render.yaml`).

## Backend — tests (10 files)

### `backend/tests/__init__.py`

* **Purpose:** Package marker.
* **Size:** 1 lines · **Status:** Active (test) — Collected by the test runner; all tests passed in this audit (2026-10-21).
* **Key symbols:** —
* **Imports (repository):** —
* **Imports (third-party/stdlib):** —
* **Imported by:** —

### `backend/tests/conftest.py`

* **Purpose:** Test harness on a real PostgreSQL test database with the least-privilege app role; fixtures for clients, accounts, trained model, outbox.
* **Size:** 206 lines · **Status:** Active (test) — Collected by the test runner; all tests passed in this audit (2026-10-21).
* **Key symbols:** `REPO` (const) L19, `BACKEND` (const) L50, `owner_engine()` L54, `migrated()` L61, `_truncate_all()` L69, `clean_db()` L80, `seeded()` L90, `trained_artifact()` L100, `readiness_model()` L109, `app()` L122, `ApiClient` (class) L128, `client()` L142, `make_client()` L148, `STRONG_PASSWORD` (const) L162, `outbox_tokens()` L165, `register()` L177, `login()` L185, `set_role()` L191, `student()` L197
* **Imports (repository):** `backend/app/db.py`, `backend/app/main.py`, `backend/app/ml/registry.py`, `backend/app/security/ratelimit.py`, `backend/app/seed/catalogue.py`, `backend/ml_pipeline/train.py`
* **Imports (third-party/stdlib):** `__future__`, `alembic`, `collections`, `dotenv`, `email`, `fastapi`, `os`, `pathlib`, `pytest`, `re`, `sqlalchemy`, `tempfile`
* **Imported by:** `backend/tests/test_auth.py`, `backend/tests/test_documents_privacy.py`, `backend/tests/test_staff_admin.py`, `backend/tests/test_twin.py`

### `backend/tests/test_auth.py`

* **Purpose:** 19 tests: registration, non-enumeration, cookies, hashing, CSRF/Origin, lockout, rate limits, reset, sessions, MFA, headers, body limits.
* **Size:** 269 lines · **Status:** Active (test) — Collected by the test runner; all tests passed in this audit (2026-10-21).
* **Key symbols:** `API` (const) L10, `test_register_is_non_enumerating_and_sends_mail()` L13, `test_weak_password_and_missing_consent_rejected()` L37, `test_unknown_fields_rejected()` L55, `test_login_errors_do_not_reveal_account_existence()` L69, `test_login_sets_hardened_cookies_and_me_works()` L78, `test_credentials_are_stored_only_as_hashes()` L93, `test_csrf_and_origin_protections()` L104, `test_logout_revokes_session()` L125, `test_lockout_after_repeated_failures()` L134, `test_login_rate_limit()` L150, `test_password_reset_flow_single_use_and_revokes_sessions()` L158, `test_expired_reset_token_rejected()` L177, `test_change_password_revokes_other_sessions()` L187, `test_sessions_are_owner_scoped()` L200, `test_email_verification()` L212, `test_mfa_enrolment_login_and_disable()` L222, `test_security_headers_and_error_envelope()` L245, `test_oversized_body_rejected()` L262, `test_unauthenticated_access_rejected()` L267
* **Imports (repository):** `backend/tests/conftest.py`
* **Imports (third-party/stdlib):** `__future__`, `datetime`, `pyotp`, `sqlalchemy`
* **Imported by:** —

### `backend/tests/test_career.py`

* **Purpose:** 15 tests: gap formula properties, alternatives, priorities, readiness with/without model, SHAP additivity, simulator isolation, scenario privacy.
* **Size:** 250 lines · **Status:** Active (test) — Collected by the test runner; all tests passed in this audit (2026-10-21).
* **Key symbols:** `API` (const) L11, `_catalogue()` L17, `_role()` L23, `_est()` L27, `test_match_bounds_and_unknown_is_not_zero()` L37, `test_alternative_group_uses_best_member()` L47, `test_prerequisite_action_and_priority_ordering()` L54, `test_optional_weight_is_configurable()` L65, `test_verify_action_for_self_reported_only()` L72, `test_pct_to_level_mapping()` L78, `_setup_student()` L85, `test_role_catalogue_is_public_and_versioned()` L115, `test_gap_analysis_api()` L123, `test_sensitivity_is_reproducible()` L142, `test_readiness_unavailable_without_model()` L150, `test_readiness_with_model()` L157, `test_shap_explanation_matches_model()` L180, `test_simulation_never_touches_real_twin()` L196, `test_simulation_validation()` L227, `test_saved_scenarios_are_private()` L242
* **Imports (repository):** `backend/app/ml/feature_schema.py`, `backend/app/services/career/gap_engine.py`, `backend/app/services/career/readiness.py`, `backend/app/services/catalogue.py`, `backend/app/services/twin/proficiency.py`
* **Imports (third-party/stdlib):** `__future__`, `math`, `numpy`, `pandas`, `sqlalchemy`
* **Imported by:** `backend/tests/test_planning.py`, `backend/tests/test_rag.py`, `backend/tests/test_staff_admin.py`

### `backend/tests/test_documents_privacy.py`

* **Purpose:** 9 tests: TXT/PDF/DOCX analysis, malicious files, document access control, JD compare, consents, export, deletion, retention.
* **Size:** 214 lines · **Status:** Active (test) — Collected by the test runner; all tests passed in this audit (2026-10-21).
* **Key symbols:** `API` (const) L14, `RESUME` (const) L16, `make_pdf()` L36, `make_docx()` L59, `upload()` L68, `test_resume_upload_txt_analysis()` L72, `test_resume_upload_pdf_and_docx()` L86, `test_malicious_and_invalid_files_rejected()` L96, `test_document_access_control_and_deletion()` L120, `test_confirm_resume_skills_and_jd_compare()` L135, `test_consents_and_attendance_purpose_limitation()` L161, `test_export_contains_own_data_without_secrets()` L172, `test_account_deletion_is_complete()` L184, `test_retention_removes_expired_documents()` L203
* **Imports (repository):** `backend/app/db.py`, `backend/app/services/privacy.py`, `backend/tests/conftest.py`, `backend/tests/test_rag.py`
* **Imports (third-party/stdlib):** `__future__`, `docx`, `io`, `os`, `pathlib`, `sqlalchemy`, `zipfile`
* **Imported by:** —

### `backend/tests/test_ml.py`

* **Purpose:** 13 tests: feature validation, generator determinism, dataset validation, protected attributes, grouped split, ECE/bootstrap, manifest honesty, reproducibility, tamper rejection, bundled-model registration, pool option, OOD.
* **Size:** 189 lines · **Status:** Active (test) — Collected by the test runner; all tests passed in this audit (2026-10-21).
* **Key symbols:** `test_feature_vector_validation()` L17, `test_synthetic_generator_is_deterministic()` L27, `test_dataset_validation_removes_bad_rows_and_reports()` L36, `test_protected_attributes_are_refused()` L49, `test_csv_source_requires_provenance()` L56, `test_grouped_split_has_no_student_leakage()` L66, `test_ece_and_bootstrap()` L76, `test_trained_artifact_manifest_is_complete_and_honest()` L86, `test_training_is_reproducible()` L101, `test_registry_rejects_tampered_or_mismatched_artifacts()` L112, `test_deploy_init_registers_shipped_model_once()` L134, `test_engine_without_pool_holds_no_idle_connections()` L158, `test_prediction_consistency_and_ood_warning()` L176
* **Imports (repository):** `backend/app/config.py`, `backend/app/db.py`, `backend/app/ml/artifacts.py`, `backend/app/ml/feature_schema.py`, `backend/app/ml/registry.py`, `backend/app/models/__init__.py`, `backend/app/services/career/readiness.py`, `backend/ml_pipeline/datasets.py`, `backend/ml_pipeline/evaluation.py`, `backend/ml_pipeline/synthetic.py`, `backend/ml_pipeline/train.py`
* **Imports (third-party/stdlib):** `__future__`, `json`, `numpy`, `pandas`, `pytest`, `shutil`, `sqlalchemy`
* **Imported by:** —

### `backend/tests/test_planning.py`

* **Purpose:** 8 tests: knowledge graph, insights, inferred edges, roadmap generation/regeneration, reorder warnings, isolation, timeline.
* **Size:** 135 lines · **Status:** Active (test) — Collected by the test runner; all tests passed in this audit (2026-10-21).
* **Key symbols:** `API` (const) L5, `test_knowledge_graph_built_from_data()` L8, `test_graph_insights_queries()` L28, `test_inferred_edges_are_labelled()` L44, `test_roadmap_generation_progress_and_regeneration()` L62, `test_roadmap_reorder_warns_on_prerequisite_violation()` L100, `test_roadmap_isolation()` L112, `test_roadmap_requires_target_role()` L121, `test_progress_timeline()` L127
* **Imports (repository):** `backend/tests/test_career.py`
* **Imports (third-party/stdlib):** `__future__`, `sqlalchemy`
* **Imported by:** —

### `backend/tests/test_rag.py`

* **Purpose:** 12 tests: chunking, PII redaction, injection detection, owner-scoped retrieval, context budget, own-data context, unverified numbers, unavailability, limits, conversation privacy, link sanitiser.
* **Size:** 203 lines · **Status:** Active (test) — Collected by the test runner; all tests passed in this audit (2026-10-21).
* **Key symbols:** `API` (const) L19, `_fake_embed()` L22, `fake_vectors()` L34, `test_chunking_respects_headings_and_size()` L43, `test_pii_redaction()` L52, `test_injection_detection_has_no_false_positives_on_kb()` L57, `test_private_retrieval_is_owner_scoped_and_injection_filtered()` L66, `test_private_documents_require_owner()` L104, `test_context_budget_fits_window()` L109, `test_student_context_contains_only_own_data()` L133, `test_unverified_numbers_flagged()` L148, `test_mentor_unavailable_returns_clear_status()` L154, `test_mentor_input_limits()` L166, `test_conversations_are_private()` L179, `test_sanitize_links_removes_uncatalogued_urls()` L193
* **Imports (repository):** `backend/app/api/v1/mentor.py`, `backend/app/config.py`, `backend/app/db.py`, `backend/app/models/__init__.py`, `backend/app/services/rag/knowledge_base.py`, `backend/app/services/rag/mentor.py`, `backend/app/services/rag/store.py`, `backend/app/services/rag/text.py`, `backend/tests/test_career.py`
* **Imports (third-party/stdlib):** `__future__`, `contextlib`, `hashlib`, `math`, `pytest`, `re`, `sqlalchemy`, `uuid`
* **Imported by:** `backend/tests/test_documents_privacy.py`

### `backend/tests/test_staff_admin.py`

* **Purpose:** 9 tests: role separation, mentor link + consent gate, admin user management, role versioning, prerequisite cycles, SSRF guard, tampered model, system status, feedback list.
* **Size:** 206 lines · **Status:** Active (test) — Collected by the test runner; all tests passed in this audit (2026-10-21).
* **Key symbols:** `API` (const) L8, `_ids()` L11, `_staff()` L16, `test_students_cannot_use_staff_or_admin_endpoints()` L24, `test_mentor_access_requires_link_and_consent()` L32, `test_admin_user_management_revokes_sessions()` L97, `test_role_versioning_and_staleness()` L110, `test_prerequisite_cycle_rejected()` L138, `test_resource_ssrf_guard()` L148, `test_model_activation_refuses_tampered_artifact()` L170, `test_admin_system_status()` L180, `test_feedback_is_listed_for_admins_anonymously_and_rate_limited()` L186
* **Imports (repository):** `backend/tests/conftest.py`, `backend/tests/test_career.py`
* **Imports (third-party/stdlib):** `__future__`, `sqlalchemy`
* **Imported by:** —

### `backend/tests/test_twin.py`

* **Purpose:** 12 tests: snapshots, validation, evidence precedence, IDOR isolation, RLS under the app role, verification reset, onboarding, completeness, partial patch.
* **Size:** 214 lines · **Status:** Active (test) — Collected by the test runner; all tests passed in this audit (2026-10-21).
* **Key symbols:** `API` (const) L7, `_skill_id()` L10, `_role_id()` L15, `test_profile_update_creates_versioned_snapshots()` L19, `test_profile_validation_and_attendance_consent()` L43, `test_unknown_vs_self_reported_vs_evidence_precedence()` L52, `test_project_validation()` L75, `test_cross_user_isolation_idor()` L90, `test_rls_blocks_cross_user_rows_under_app_role()` L100, `test_verified_item_edit_resets_verification()` L139, `test_role_preferences_and_onboarding()` L148, `test_self_reported_assessment_is_unverified()` L159, `test_completeness()` L172, `test_profile_patch_is_partial()` L192, `test_login_response_reflects_completed_onboarding()` L201
* **Imports (repository):** `backend/tests/conftest.py`
* **Imports (third-party/stdlib):** `__future__`, `datetime`, `sqlalchemy`
* **Imported by:** —

## Frontend — configuration and tooling (15 files)

### `frontend/.dockerignore`

* **Purpose:** Excludes node_modules, build output and test reports from the web image build context.
* **Size:** 5 lines · **Status:** Active (configuration) — Read by the tool named in the purpose.

### `frontend/Dockerfile`

* **Purpose:** Two-stage web image: Node builds the SPA, unprivileged nginx serves it.
* **Size:** 16 lines · **Status:** Active (configuration) — Read by the tool named in the purpose.

### `frontend/e2e/student-journey.spec.ts`

* **Purpose:** Playwright end-to-end journey: register/onboard, twin + gaps + readiness + simulation + roadmap, CSRF rejection, keyboard skip link (desktop + mobile), account deletion.
* **Size:** 146 lines · **Status:** Active (test) — Collected by the test runner; all tests passed in this audit (2026-10-21).
* **Key symbols:** —
* **Imports (repository):** —
* **Imports (third-party/stdlib):** `@playwright/test`, `node:crypto`
* **Imported by:** —

### `frontend/eslint.config.js`

* **Purpose:** ESLint flat config (TypeScript, React hooks) including a ban on `dangerouslySetInnerHTML`.
* **Size:** 25 lines · **Status:** Active (configuration) — Read by the tool named in the purpose.

### `frontend/index.html`

* **Purpose:** HTML shell: title, description, theme, `#root` mount point and the module script.
* **Size:** 17 lines · **Status:** Active (configuration) — Read by the tool named in the purpose.

### `frontend/nginx.conf`

* **Purpose:** nginx for the web container: strict CSP and security headers, SPA fallback, `/api` reverse proxy, SSE-friendly mentor location.
* **Size:** 74 lines · **Status:** Active (configuration) — Read by the tool named in the purpose.

### `frontend/package-lock.json`

* **Purpose:** Generated npm lockfile pinning every frontend dependency.
* **Size:** 7626 lines · **Status:** Generated — Produced by a tool or pipeline run; regenerate rather than edit by hand.

### `frontend/package.json`

* **Purpose:** Frontend dependencies (React 19, Vite 8, Tailwind 4, TanStack Query, Radix, R3F/drei/three, Recharts, Motion, RHF + Zod) and scripts.
* **Size:** 66 lines · **Status:** Active (configuration) — Read by the tool named in the purpose.

### `frontend/playwright.config.ts`

* **Purpose:** Playwright projects (desktop Chrome, mobile Pixel 7 for `@responsive` tests) and `E2E_BASE_URL`.
* **Size:** 26 lines · **Status:** Active (entry point) — Loaded by Playwright.
* **Key symbols:** —
* **Imports (repository):** —
* **Imports (third-party/stdlib):** `@playwright/test`
* **Imported by:** —

### `frontend/public/favicon.svg`

* **Purpose:** Favicon (the two-circle brand mark).
* **Size:** 12 lines · **Status:** Active (configuration) — Read by the tool named in the purpose.

### `frontend/tsconfig.app.json`

* **Purpose:** TypeScript strict configuration for the application source (`@/` path alias).
* **Size:** 25 lines · **Status:** Active (configuration) — Read by the tool named in the purpose.

### `frontend/tsconfig.json`

* **Purpose:** TypeScript project references root.
* **Size:** 4 lines · **Status:** Active (configuration) — Read by the tool named in the purpose.

### `frontend/tsconfig.node.json`

* **Purpose:** TypeScript configuration for Vite/Playwright config files and e2e tests.
* **Size:** 16 lines · **Status:** Active (configuration) — Read by the tool named in the purpose.

### `frontend/vercel.json`

* **Purpose:** Vercel configuration: Vite build, `/api/*` rewrite to the Render API, SPA fallback, security headers.
* **Size:** 31 lines · **Status:** Active (configuration) — Read by the tool named in the purpose.

### `frontend/vite.config.ts`

* **Purpose:** Vite + React + Tailwind plugins, `/api` dev proxy to 127.0.0.1:8010, `@` alias, Vitest (jsdom) configuration.
* **Size:** 38 lines · **Status:** Active (entry point) — Loaded by Vite/Vitest.
* **Key symbols:** —
* **Imports (repository):** —
* **Imports (third-party/stdlib):** `@tailwindcss/vite`, `@vitejs/plugin-react`, `node:url`, `vite`
* **Imported by:** —

## Frontend — application core and libraries (13 files)

### `frontend/src/lib/api.test.ts`

* **Purpose:** 5 tests for the API client (CSRF headers, error envelope, retry, offline, cookie preference).
* **Size:** 59 lines · **Status:** Active (test) — Collected by the test runner; all tests passed in this audit (2026-10-21).
* **Key symbols:** —
* **Imports (repository):** `frontend/src/lib/api.ts`, `frontend/src/test/utils.tsx`
* **Imports (third-party/stdlib):** `vitest`
* **Imported by:** —

### `frontend/src/lib/api.ts`

* **Purpose:** Typed fetch client: same-origin cookies, `X-Requested-With` + CSRF header on unsafe methods, error envelope normalisation, one CSRF refresh retry, file download helper.
* **Size:** 143 lines · **Status:** Active — Imported by 28 file(s).
* **Key symbols:** `API_BASE` (const) L10, `ApiError` (class) L12, `readCookie` (function) L38, `csrfToken` (function) L47, `RequestOptions` (interface) L53, `headersFor` (function) L86, `api` (function) L101, `download` (function) L130
* **Imports (repository):** —
* **Imports (third-party/stdlib):** —
* **Imported by:** `frontend/src/components/FeedbackButton.tsx`, `frontend/src/components/components.test.tsx`, `frontend/src/components/layout/AppShell.tsx`, `frontend/src/components/ui/states.tsx`, `frontend/src/lib/api.test.ts`, `frontend/src/lib/queries.ts`, `frontend/src/lib/sse.ts`, `frontend/src/pages/admin/AdminPage.tsx`, `frontend/src/pages/auth/AuthPages.tsx`, `frontend/src/pages/dashboard/DashboardPage.tsx`, `frontend/src/pages/documents/DocumentsPage.tsx`, `frontend/src/pages/graph/GraphPage.tsx`, `frontend/src/pages/landing/LandingPage.tsx`, `frontend/src/pages/mentor/MentorPage.tsx`, `frontend/src/pages/onboarding/OnboardingPage.tsx`, `frontend/src/pages/progress/ProgressPage.tsx`, `frontend/src/pages/readiness/ModelCardPage.tsx`, `frontend/src/pages/readiness/ReadinessPage.tsx`, `frontend/src/pages/roadmap/RoadmapPage.tsx`, `frontend/src/pages/roles/RolesPage.tsx`, `frontend/src/pages/settings/SettingsPage.tsx`, `frontend/src/pages/simulator/SimulatorPage.tsx`, `frontend/src/pages/staff/StaffPage.tsx`, `frontend/src/pages/twin/sections/AcademicSection.tsx`, `frontend/src/pages/twin/sections/AssessmentsSection.tsx`, `frontend/src/pages/twin/sections/EvidenceSections.tsx`, `frontend/src/pages/twin/sections/HistorySection.tsx`, `frontend/src/pages/twin/sections/SkillsSection.tsx`

### `frontend/src/lib/queries.ts`

* **Purpose:** Shared TanStack Query client, query keys and hooks for the main read endpoints; twin invalidation helper.
* **Size:** 131 lines · **Status:** Active — Imported by 24 file(s).
* **Key symbols:** `queryClient` (const) L24, `qk` (const) L37, `invalidateTwin` (function) L64, `useMe` (function) L76, `useProfile` (const) L91, `useSkills` (const) L92, `useCompleteness` (const) L94, `useProjects` (const) L95, `useExperiences` (const) L96, `useCertifications` (const) L97, `useAssessments` (const) L98, `useFeatures` (const) L100, `useRoles` (const) L101, `useCatalogueSkills` (const) L107, `useLatestReadiness` (const) L109, `useMatches` (const) L110, `useRoleGaps` (const) L115, `useRoadmap` (const) L122, `useMentorStatus` (const) L123
* **Imports (repository):** `frontend/src/lib/api.ts`, `frontend/src/lib/types.ts`
* **Imports (third-party/stdlib):** `@tanstack/react-query`
* **Imported by:** `frontend/src/components/layout/AppShell.tsx`, `frontend/src/components/layout/guards.tsx`, `frontend/src/main.tsx`, `frontend/src/pages/admin/AdminPage.tsx`, `frontend/src/pages/auth/AuthPages.tsx`, `frontend/src/pages/dashboard/DashboardPage.tsx`, `frontend/src/pages/documents/DocumentsPage.tsx`, `frontend/src/pages/gaps/SkillGapsPage.tsx`, `frontend/src/pages/graph/GraphPage.tsx`, `frontend/src/pages/landing/LandingPage.tsx`, `frontend/src/pages/mentor/MentorPage.tsx`, `frontend/src/pages/onboarding/OnboardingPage.tsx`, `frontend/src/pages/progress/ProgressPage.tsx`, `frontend/src/pages/readiness/ReadinessPage.tsx`, `frontend/src/pages/roadmap/RoadmapPage.tsx`, `frontend/src/pages/roles/RolesPage.tsx`, `frontend/src/pages/settings/SettingsPage.tsx`, `frontend/src/pages/simulator/SimulatorPage.tsx`, `frontend/src/pages/twin/ProfilePage.tsx`, `frontend/src/pages/twin/sections/AcademicSection.tsx`, `frontend/src/pages/twin/sections/AssessmentsSection.tsx`, `frontend/src/pages/twin/sections/EvidenceSections.tsx`, `frontend/src/pages/twin/sections/HistorySection.tsx`, `frontend/src/pages/twin/sections/SkillsSection.tsx`

### `frontend/src/lib/sse.ts`

* **Purpose:** POST-based Server-Sent-Events reader for streamed mentor answers.
* **Size:** 60 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `SseHandlers` (interface) L3, `postSse` (function) L11
* **Imports (repository):** `frontend/src/lib/api.ts`
* **Imports (third-party/stdlib):** —
* **Imported by:** `frontend/src/pages/mentor/MentorPage.tsx`

### `frontend/src/lib/types.ts`

* **Purpose:** TypeScript types mirroring the API responses.
* **Size:** 456 lines · **Status:** Active — Imported by 26 file(s).
* **Key symbols:** `Role` (type) L1, `User` (interface) L3, `Me` (interface) L13, `LoginResult` (interface) L20, `Profile` (interface) L26, `Signal` (interface) L45, `SkillItem` (interface) L56, `ScaleLevel` (interface) L70, `Requirement` (interface) L76, `CareerRole` (interface) L89, `CatalogueSkill` (interface) L100, `EvidenceLink` (interface) L110, `Verification` (type) L117, `Project` (interface) L119, `Experience` (interface) L135, `Certification` (interface) L148, `AssessmentResult` (interface) L159, `AssessmentDef` (interface) L173, `Completeness` (interface) L183, `Resource` (interface) L191, `Gap` (interface) L202, `RoleGapAnalysis` (interface) L231, `RoleMatchSummary` (interface) L248, `Contribution` (interface) L263, `Warning` (interface) L273, `ReadinessResult` (interface) L279, `LatestReadiness` (interface) L301, `FeatureRow` (interface) L316, `RoadmapItem` (interface) L326, `Roadmap` (interface) L350, `RoadmapComparison` (interface) L373, `GraphNode` (interface) L380, `GraphEdge` (interface) L397, `GraphPayload` (interface) L409, `MentorSource` (interface) L417, `DocumentItem` (interface) L426, `Paged` (interface) L451
* **Imports (repository):** —
* **Imports (third-party/stdlib):** —
* **Imported by:** `frontend/src/components/charts/ShapChart.tsx`, `frontend/src/components/components.test.tsx`, `frontend/src/components/layout/AppShell.tsx`, `frontend/src/components/layout/guards.test.tsx`, `frontend/src/components/layout/guards.tsx`, `frontend/src/components/three/ConstellationFallback.tsx`, `frontend/src/components/three/Graph2D.tsx`, `frontend/src/components/three/Graph3D.tsx`, `frontend/src/components/three/SkillConstellation.tsx`, `frontend/src/components/three/constellationLayout.ts`, `frontend/src/components/three/graphStyle.ts`, `frontend/src/components/twin/TwinVisual.tsx`, `frontend/src/lib/queries.ts`, `frontend/src/pages/admin/AdminPage.tsx`, `frontend/src/pages/auth/AuthPages.tsx`, `frontend/src/pages/dashboard/DashboardPage.tsx`, `frontend/src/pages/documents/DocumentsPage.tsx`, `frontend/src/pages/gaps/SkillGapsPage.tsx`, `frontend/src/pages/graph/GraphPage.tsx`, `frontend/src/pages/mentor/MentorPage.tsx`, `frontend/src/pages/onboarding/OnboardingPage.tsx`, `frontend/src/pages/readiness/ReadinessPage.tsx`, `frontend/src/pages/roadmap/RoadmapPage.tsx`, `frontend/src/pages/roles/RolesPage.tsx`, `frontend/src/pages/twin/sections/EvidenceSections.tsx`, `frontend/src/pages/twin/sections/SkillsSection.tsx`

### `frontend/src/lib/utils.ts`

* **Purpose:** Class-name merging, category/level/status/action/band display metadata, number and date formatting.
* **Size:** 83 lines · **Status:** Active — Imported by 33 file(s).
* **Key symbols:** `cn` (function) L4, `CATEGORY_LABEL` (const) L8, `CATEGORY_COLOR` (const) L20, `LEVEL_NAMES` (const) L32, `STATUS_META` (const) L34, `ACTION_META` (const) L42, `BAND_META` (const) L50, `pct` (function) L56, `level` (function) L61, `dateTime` (function) L66, `dateOnly` (function) L71, `relative` (function) L76
* **Imports (repository):** —
* **Imports (third-party/stdlib):** `clsx`, `tailwind-merge`
* **Imported by:** `frontend/src/components/FeedbackButton.tsx`, `frontend/src/components/PasswordChecklist.tsx`, `frontend/src/components/charts/CategoryRadar.tsx`, `frontend/src/components/layout/AppShell.tsx`, `frontend/src/components/layout/Brand.tsx`, `frontend/src/components/three/ConstellationFallback.tsx`, `frontend/src/components/three/SkillConstellation.tsx`, `frontend/src/components/three/TwinCore.tsx`, `frontend/src/components/three/graphStyle.ts`, `frontend/src/components/ui/button.tsx`, `frontend/src/components/ui/form.tsx`, `frontend/src/components/ui/overlay.tsx`, `frontend/src/components/ui/primitives.tsx`, `frontend/src/components/ui/states.tsx`, `frontend/src/pages/admin/AdminPage.tsx`, `frontend/src/pages/dashboard/DashboardPage.tsx`, `frontend/src/pages/documents/DocumentsPage.tsx`, `frontend/src/pages/gaps/SkillGapsPage.tsx`, `frontend/src/pages/graph/GraphPage.tsx`, `frontend/src/pages/mentor/MentorPage.tsx`, `frontend/src/pages/onboarding/OnboardingPage.tsx`, `frontend/src/pages/progress/ProgressPage.tsx`, `frontend/src/pages/readiness/ModelCardPage.tsx`, `frontend/src/pages/readiness/ReadinessPage.tsx`, `frontend/src/pages/roadmap/RoadmapPage.tsx`, `frontend/src/pages/roles/RolesPage.tsx`, `frontend/src/pages/settings/SettingsPage.tsx`, `frontend/src/pages/simulator/SimulatorPage.tsx`, `frontend/src/pages/staff/StaffPage.tsx`, `frontend/src/pages/twin/sections/AssessmentsSection.tsx`, `frontend/src/pages/twin/sections/EvidenceSections.tsx`, `frontend/src/pages/twin/sections/HistorySection.tsx`, `frontend/src/pages/twin/sections/SkillsSection.tsx`

### `frontend/src/lib/visuals.test.tsx`

* **Purpose:** 2 tests for the 3D fallback decision.
* **Size:** 31 lines · **Status:** Active (test) — Collected by the test runner; all tests passed in this audit (2026-10-21).
* **Key symbols:** —
* **Imports (repository):** `frontend/src/lib/visuals.ts`
* **Imports (third-party/stdlib):** `@testing-library/react`, `vitest`
* **Imported by:** —

### `frontend/src/lib/visuals.ts`

* **Purpose:** 3D capability detection (`useCan3D`): user preference, WebGL support, reduced motion, device memory.
* **Size:** 77 lines · **Status:** Active — Imported by 5 file(s).
* **Key symbols:** `setVisualsPref` (function) L20, `useVisualsPref` (function) L30, `supportsWebGL` (function) L42, `usePrefersReducedMotion` (function) L53, `useCan3D` (function) L67
* **Imports (repository):** —
* **Imports (third-party/stdlib):** `react`
* **Imported by:** `frontend/src/components/twin/TwinVisual.tsx`, `frontend/src/lib/visuals.test.tsx`, `frontend/src/pages/graph/GraphPage.tsx`, `frontend/src/pages/landing/LandingPage.tsx`, `frontend/src/pages/settings/SettingsPage.tsx`

### `frontend/src/main.tsx`

* **Purpose:** Entry point: mounts React with TanStack Query, Motion (respects reduced motion), Radix tooltips, router and toasts.
* **Size:** 29 lines · **Status:** Active (entry point) — Loaded by `index.html`.
* **Key symbols:** —
* **Imports (repository):** `frontend/src/lib/queries.ts`, `frontend/src/router.tsx`, `frontend/src/styles/index.css`
* **Imports (third-party/stdlib):** `@tanstack/react-query`, `motion`, `radix-ui`, `react`, `react-dom`, `react-router`, `sonner`
* **Imported by:** —

### `frontend/src/router.tsx`

* **Purpose:** Route table with lazily loaded pages, guest/auth/role guards, onboarding route, error and 404 pages.
* **Size:** 115 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `router` (const) L51
* **Imports (repository):** `frontend/src/components/layout/AppShell.tsx`, `frontend/src/components/layout/guards.tsx`, `frontend/src/components/ui/states.tsx`, `frontend/src/pages/admin/AdminPage.tsx`, `frontend/src/pages/auth/AuthPages.tsx`, `frontend/src/pages/dashboard/DashboardPage.tsx`, `frontend/src/pages/documents/DocumentsPage.tsx`, `frontend/src/pages/errors.tsx`, `frontend/src/pages/gaps/SkillGapsPage.tsx`, `frontend/src/pages/graph/GraphPage.tsx`, `frontend/src/pages/landing/LandingPage.tsx`, `frontend/src/pages/mentor/MentorPage.tsx`, `frontend/src/pages/onboarding/OnboardingPage.tsx`, `frontend/src/pages/progress/ProgressPage.tsx`, `frontend/src/pages/readiness/ModelCardPage.tsx`, `frontend/src/pages/readiness/ReadinessPage.tsx`, `frontend/src/pages/roadmap/RoadmapPage.tsx`, `frontend/src/pages/roles/RolesPage.tsx`, `frontend/src/pages/settings/SettingsPage.tsx`, `frontend/src/pages/simulator/SimulatorPage.tsx`, `frontend/src/pages/staff/StaffPage.tsx`, `frontend/src/pages/twin/ProfilePage.tsx`
* **Imports (third-party/stdlib):** `react`, `react-router`
* **Imported by:** `frontend/src/main.tsx`

### `frontend/src/styles/index.css`

* **Purpose:** Tailwind 4 theme tokens (colours, fonts, radii, motion), base styles and utilities.
* **Size:** 142 lines · **Status:** Active (configuration) — Read by the tool named in the purpose.

### `frontend/src/test/setup.ts`

* **Purpose:** Vitest setup: registers jest-dom matchers (loaded via `vite.config.ts`).
* **Size:** 1 lines · **Status:** Active (entry point) — Loaded by Vitest (`setupFiles`).
* **Key symbols:** —
* **Imports (repository):** —
* **Imports (third-party/stdlib):** `@testing-library/jest-dom`
* **Imported by:** —

### `frontend/src/test/utils.tsx`

* **Purpose:** Test helpers: render with providers, axe accessibility check, JSON response factory.
* **Size:** 28 lines · **Status:** Active — Imported by 5 file(s).
* **Key symbols:** `renderWithProviders` (function) L8, `axeViolations` (function) L21, `jsonResponse` (function) L26
* **Imports (repository):** —
* **Imports (third-party/stdlib):** `@tanstack/react-query`, `@testing-library/react`, `axe-core`, `radix-ui`, `react`, `react-router`
* **Imported by:** `frontend/src/components/FeedbackButton.test.tsx`, `frontend/src/components/components.test.tsx`, `frontend/src/components/layout/guards.test.tsx`, `frontend/src/lib/api.test.ts`, `frontend/src/pages/auth/auth.test.tsx`

## Frontend — components (26 files)

### `frontend/src/components/FeedbackButton.test.tsx`

* **Purpose:** 1 test: rating required, area pre-selected from the page, correct request, accessible dialog.
* **Size:** 32 lines · **Status:** Active (test) — Collected by the test runner; all tests passed in this audit (2026-10-21).
* **Key symbols:** —
* **Imports (repository):** `frontend/src/components/FeedbackButton.tsx`, `frontend/src/test/utils.tsx`
* **Imports (third-party/stdlib):** `@testing-library/react`, `@testing-library/user-event`, `vitest`
* **Imported by:** —

### `frontend/src/components/FeedbackButton.tsx`

* **Purpose:** "Send feedback" button and dialog (area, 1–5 rating, comment) used in the app shell.
* **Size:** 112 lines · **Status:** Active — Imported by 3 file(s).
* **Key symbols:** `FEEDBACK_AREAS` (const) L13, `FeedbackButton` (function) L97
* **Imports (repository):** `frontend/src/components/ui/button.tsx`, `frontend/src/components/ui/form.tsx`, `frontend/src/components/ui/overlay.tsx`, `frontend/src/lib/api.ts`, `frontend/src/lib/utils.ts`
* **Imports (third-party/stdlib):** `lucide-react`, `react`, `react-router`, `sonner`
* **Imported by:** `frontend/src/components/FeedbackButton.test.tsx`, `frontend/src/components/layout/AppShell.tsx`, `frontend/src/pages/admin/AdminPage.tsx`

### `frontend/src/components/PasswordChecklist.tsx`

* **Purpose:** Live password-policy checklist and shared Zod password schema.
* **Size:** 35 lines · **Status:** Active — Imported by 3 file(s).
* **Key symbols:** `passwordChecks` (function) L9, `passwordSchema` (const) L20, `PasswordChecklist` (function) L22
* **Imports (repository):** `frontend/src/lib/utils.ts`
* **Imports (third-party/stdlib):** `lucide-react`, `zod`
* **Imported by:** `frontend/src/components/components.test.tsx`, `frontend/src/pages/auth/AuthPages.tsx`, `frontend/src/pages/settings/SettingsPage.tsx`

### `frontend/src/components/SafeMarkdown.tsx`

* **Purpose:** Renders model output as a safe markdown subset (no HTML; only https links) with clickable citations.
* **Size:** 72 lines · **Status:** Active — Imported by 2 file(s).
* **Key symbols:** `SafeMarkdown` (function) L44
* **Imports (repository):** —
* **Imports (third-party/stdlib):** `react`
* **Imported by:** `frontend/src/components/components.test.tsx`, `frontend/src/pages/mentor/MentorPage.tsx`

### `frontend/src/components/charts/CategoryRadar.tsx`

* **Purpose:** Recharts radar of category levels (2D alternative to the 3D constellation).
* **Size:** 36 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `CategoryRadar` (function) L8
* **Imports (repository):** `frontend/src/components/three/TwinCore.tsx`, `frontend/src/lib/utils.ts`
* **Imports (third-party/stdlib):** `recharts`
* **Imported by:** `frontend/src/components/twin/TwinVisual.tsx`

### `frontend/src/components/charts/Ring.tsx`

* **Purpose:** SVG progress ring (completeness, probabilities).
* **Size:** 37 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `Ring` (function) L5
* **Imports (repository):** —
* **Imports (third-party/stdlib):** `motion`, `react`
* **Imported by:** `frontend/src/pages/dashboard/DashboardPage.tsx`

### `frontend/src/components/charts/ShapChart.tsx`

* **Purpose:** Recharts bar chart of SHAP contributions.
* **Size:** 28 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `ShapChart` (function) L5
* **Imports (repository):** `frontend/src/lib/types.ts`
* **Imports (third-party/stdlib):** `recharts`
* **Imported by:** `frontend/src/pages/readiness/ReadinessPage.tsx`

### `frontend/src/components/components.test.tsx`

* **Purpose:** 9 component tests (SafeMarkdown safety, level meter, states, password checklist, Graph2D keyboard and inferred edges).
* **Size:** 97 lines · **Status:** Active (test) — Collected by the test runner; all tests passed in this audit (2026-10-21).
* **Key symbols:** —
* **Imports (repository):** `frontend/src/components/PasswordChecklist.tsx`, `frontend/src/components/SafeMarkdown.tsx`, `frontend/src/components/three/Graph2D.tsx`, `frontend/src/components/ui/primitives.tsx`, `frontend/src/components/ui/states.tsx`, `frontend/src/lib/api.ts`, `frontend/src/lib/types.ts`, `frontend/src/test/utils.tsx`
* **Imports (third-party/stdlib):** `@testing-library/react`, `radix-ui`, `vitest`
* **Imported by:** —

### `frontend/src/components/layout/AppShell.tsx`

* **Purpose:** Authenticated layout: sidebar navigation by role, mentor status, feedback button, user block, mobile drawer, `PageHeader`.
* **Size:** 265 lines · **Status:** Active — Imported by 16 file(s).
* **Key symbols:** `AppShell` (function) L139, `PageHeader` (function) L240
* **Imports (repository):** `frontend/src/components/FeedbackButton.tsx`, `frontend/src/components/layout/Brand.tsx`, `frontend/src/components/ui/button.tsx`, `frontend/src/lib/api.ts`, `frontend/src/lib/queries.ts`, `frontend/src/lib/types.ts`, `frontend/src/lib/utils.ts`
* **Imports (third-party/stdlib):** `@tanstack/react-query`, `lucide-react`, `motion`, `radix-ui`, `react`, `react-router`, `sonner`
* **Imported by:** `frontend/src/pages/admin/AdminPage.tsx`, `frontend/src/pages/dashboard/DashboardPage.tsx`, `frontend/src/pages/documents/DocumentsPage.tsx`, `frontend/src/pages/gaps/SkillGapsPage.tsx`, `frontend/src/pages/graph/GraphPage.tsx`, `frontend/src/pages/mentor/MentorPage.tsx`, `frontend/src/pages/progress/ProgressPage.tsx`, `frontend/src/pages/readiness/ModelCardPage.tsx`, `frontend/src/pages/readiness/ReadinessPage.tsx`, `frontend/src/pages/roadmap/RoadmapPage.tsx`, `frontend/src/pages/roles/RolesPage.tsx`, `frontend/src/pages/settings/SettingsPage.tsx`, `frontend/src/pages/simulator/SimulatorPage.tsx`, `frontend/src/pages/staff/StaffPage.tsx`, `frontend/src/pages/twin/ProfilePage.tsx`, `frontend/src/router.tsx`

### `frontend/src/components/layout/Brand.tsx`

* **Purpose:** Brand mark and wordmark linking home.
* **Size:** 37 lines · **Status:** Active — Imported by 5 file(s).
* **Key symbols:** `BrandMark` (function) L6, `Brand` (function) L25
* **Imports (repository):** `frontend/src/lib/utils.ts`
* **Imports (third-party/stdlib):** `react`, `react-router`
* **Imported by:** `frontend/src/components/layout/AppShell.tsx`, `frontend/src/pages/auth/AuthPages.tsx`, `frontend/src/pages/errors.tsx`, `frontend/src/pages/landing/LandingPage.tsx`, `frontend/src/pages/onboarding/OnboardingPage.tsx`

### `frontend/src/components/layout/guards.test.tsx`

* **Purpose:** 3 tests for onboarding/staff routing in `RequireAuth`.
* **Size:** 48 lines · **Status:** Active (test) — Collected by the test runner; all tests passed in this audit (2026-10-21).
* **Key symbols:** —
* **Imports (repository):** `frontend/src/components/layout/guards.tsx`, `frontend/src/lib/types.ts`, `frontend/src/test/utils.tsx`
* **Imports (third-party/stdlib):** `@testing-library/react`, `react-router`, `vitest`
* **Imported by:** —

### `frontend/src/components/layout/guards.tsx`

* **Purpose:** `RequireAuth` (login, role and onboarding redirects) and `RedirectIfAuthed`.
* **Size:** 34 lines · **Status:** Active — Imported by 2 file(s).
* **Key symbols:** `RequireAuth` (function) L16, `RedirectIfAuthed` (function) L29
* **Imports (repository):** `frontend/src/components/ui/states.tsx`, `frontend/src/lib/queries.ts`, `frontend/src/lib/types.ts`
* **Imports (third-party/stdlib):** `react`, `react-router`
* **Imported by:** `frontend/src/components/layout/guards.test.tsx`, `frontend/src/router.tsx`

### `frontend/src/components/motion.tsx`

* **Purpose:** Reveal/stagger animation helpers (Motion).
* **Size:** 47 lines · **Status:** Active — Imported by 4 file(s).
* **Key symbols:** `Reveal` (function) L7, `staggerParent` (const) L23, `staggerChild` (const) L28, `Stagger` (function) L33, `StaggerItem` (function) L41
* **Imports (repository):** —
* **Imports (third-party/stdlib):** `motion`, `react`
* **Imported by:** `frontend/src/pages/dashboard/DashboardPage.tsx`, `frontend/src/pages/landing/LandingPage.tsx`, `frontend/src/pages/readiness/ReadinessPage.tsx`, `frontend/src/pages/roles/RolesPage.tsx`

### `frontend/src/components/three/ConstellationFallback.tsx`

* **Purpose:** 2D fallback for the skill constellation.
* **Size:** 36 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `ConstellationFallback` (function) L9
* **Imports (repository):** `frontend/src/components/three/constellationLayout.ts`, `frontend/src/lib/types.ts`, `frontend/src/lib/utils.ts`
* **Imports (third-party/stdlib):** `react`
* **Imported by:** `frontend/src/pages/landing/LandingPage.tsx`

### `frontend/src/components/three/Graph2D.tsx`

* **Purpose:** Keyboard-accessible 2D knowledge-graph view.
* **Size:** 45 lines · **Status:** Active — Imported by 2 file(s).
* **Key symbols:** `Graph2D` (function) L9
* **Imports (repository):** `frontend/src/components/three/graphStyle.ts`, `frontend/src/lib/types.ts`
* **Imports (third-party/stdlib):** `react`
* **Imported by:** `frontend/src/components/components.test.tsx`, `frontend/src/pages/graph/GraphPage.tsx`

### `frontend/src/components/three/Graph3D.tsx`

* **Purpose:** React Three Fiber 3D knowledge-graph view using server-computed positions.
* **Size:** 91 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `Graph3D` (function) L39
* **Imports (repository):** `frontend/src/components/three/graphStyle.ts`, `frontend/src/lib/types.ts`
* **Imports (third-party/stdlib):** `@react-three/drei`, `@react-three/fiber`, `react`, `three`
* **Imported by:** `frontend/src/pages/graph/GraphPage.tsx`

### `frontend/src/components/three/SkillConstellation.tsx`

* **Purpose:** R3F 3D skill constellation on the dashboard.
* **Size:** 94 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `SkillConstellation` (function) L75
* **Imports (repository):** `frontend/src/components/three/constellationLayout.ts`, `frontend/src/lib/types.ts`, `frontend/src/lib/utils.ts`
* **Imports (third-party/stdlib):** `@react-three/drei`, `@react-three/fiber`, `react`, `three`
* **Imported by:** `frontend/src/pages/landing/LandingPage.tsx`

### `frontend/src/components/three/TwinCore.tsx`

* **Purpose:** R3F 3D 'twin core' visual of category levels.
* **Size:** 113 lines · **Status:** Active — Imported by 2 file(s).
* **Key symbols:** `TwinAxis` (interface) L8, `TwinCore` (function) L102
* **Imports (repository):** `frontend/src/lib/utils.ts`
* **Imports (third-party/stdlib):** `@react-three/drei`, `@react-three/fiber`, `react`, `three`
* **Imported by:** `frontend/src/components/charts/CategoryRadar.tsx`, `frontend/src/components/twin/TwinVisual.tsx`

### `frontend/src/components/three/constellationLayout.ts`

* **Purpose:** Deterministic layout for constellation nodes and edges.
* **Size:** 63 lines · **Status:** Active — Imported by 2 file(s).
* **Key symbols:** `CNode` (interface) L3, `CEdge` (interface) L12, `constellationLayout` (function) L25
* **Imports (repository):** `frontend/src/lib/types.ts`
* **Imports (third-party/stdlib):** —
* **Imported by:** `frontend/src/components/three/ConstellationFallback.tsx`, `frontend/src/components/three/SkillConstellation.tsx`

### `frontend/src/components/three/graphStyle.ts`

* **Purpose:** Shared node/edge colours and sizes for graph views.
* **Size:** 44 lines · **Status:** Active — Imported by 3 file(s).
* **Key symbols:** `TYPE_COLOR` (const) L4, `nodeColor` (function) L12, `nodeSize` (function) L20, `edgeColor` (function) L33
* **Imports (repository):** `frontend/src/lib/types.ts`, `frontend/src/lib/utils.ts`
* **Imports (third-party/stdlib):** —
* **Imported by:** `frontend/src/components/three/Graph2D.tsx`, `frontend/src/components/three/Graph3D.tsx`, `frontend/src/pages/graph/GraphPage.tsx`

### `frontend/src/components/twin/TwinVisual.tsx`

* **Purpose:** Chooses 3D (TwinCore) or 2D (CategoryRadar) based on `useCan3D`.
* **Size:** 46 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `useTwinAxes` (function) L13, `TwinVisual` (function) L25
* **Imports (repository):** `frontend/src/components/charts/CategoryRadar.tsx`, `frontend/src/components/three/TwinCore.tsx`, `frontend/src/components/ui/states.tsx`, `frontend/src/lib/types.ts`, `frontend/src/lib/visuals.ts`
* **Imports (third-party/stdlib):** `motion`, `react`
* **Imported by:** `frontend/src/pages/dashboard/DashboardPage.tsx`

### `frontend/src/components/ui/button.tsx`

* **Purpose:** Button component with variants, sizes and loading state.
* **Size:** 61 lines · **Status:** Active — Imported by 24 file(s).
* **Key symbols:** `ButtonProps` (interface) L24, `Button` (const) L31
* **Imports (repository):** `frontend/src/lib/utils.ts`
* **Imports (third-party/stdlib):** `lucide-react`, `radix-ui`, `react`
* **Imported by:** `frontend/src/components/FeedbackButton.tsx`, `frontend/src/components/layout/AppShell.tsx`, `frontend/src/components/ui/overlay.tsx`, `frontend/src/components/ui/states.tsx`, `frontend/src/pages/admin/AdminPage.tsx`, `frontend/src/pages/auth/AuthPages.tsx`, `frontend/src/pages/dashboard/DashboardPage.tsx`, `frontend/src/pages/documents/DocumentsPage.tsx`, `frontend/src/pages/errors.tsx`, `frontend/src/pages/gaps/SkillGapsPage.tsx`, `frontend/src/pages/graph/GraphPage.tsx`, `frontend/src/pages/landing/LandingPage.tsx`, `frontend/src/pages/mentor/MentorPage.tsx`, `frontend/src/pages/onboarding/OnboardingPage.tsx`, `frontend/src/pages/readiness/ReadinessPage.tsx`, `frontend/src/pages/roadmap/RoadmapPage.tsx`, `frontend/src/pages/roles/RolesPage.tsx`, `frontend/src/pages/settings/SettingsPage.tsx`, `frontend/src/pages/simulator/SimulatorPage.tsx`, `frontend/src/pages/staff/StaffPage.tsx`, `frontend/src/pages/twin/sections/AcademicSection.tsx`, `frontend/src/pages/twin/sections/AssessmentsSection.tsx`, `frontend/src/pages/twin/sections/EvidenceSections.tsx`, `frontend/src/pages/twin/sections/SkillsSection.tsx`

### `frontend/src/components/ui/form.tsx`

* **Purpose:** Accessible form controls: Input, Textarea, Select, Field (label/hint/error wiring), Slider, Switch.
* **Size:** 140 lines · **Status:** Active — Imported by 18 file(s).
* **Key symbols:** `Input` (const) L11, `Textarea` (const) L15, `Select` (const) L22, `Field` (function) L37, `Slider` (function) L76, `Switch` (function) L128
* **Imports (repository):** `frontend/src/lib/utils.ts`
* **Imports (third-party/stdlib):** `radix-ui`, `react`
* **Imported by:** `frontend/src/components/FeedbackButton.tsx`, `frontend/src/pages/admin/AdminPage.tsx`, `frontend/src/pages/auth/AuthPages.tsx`, `frontend/src/pages/documents/DocumentsPage.tsx`, `frontend/src/pages/gaps/SkillGapsPage.tsx`, `frontend/src/pages/graph/GraphPage.tsx`, `frontend/src/pages/mentor/MentorPage.tsx`, `frontend/src/pages/onboarding/OnboardingPage.tsx`, `frontend/src/pages/progress/ProgressPage.tsx`, `frontend/src/pages/roadmap/RoadmapPage.tsx`, `frontend/src/pages/settings/SettingsPage.tsx`, `frontend/src/pages/simulator/SimulatorPage.tsx`, `frontend/src/pages/staff/StaffPage.tsx`, `frontend/src/pages/twin/sections/AcademicSection.tsx`, `frontend/src/pages/twin/sections/AssessmentsSection.tsx`, `frontend/src/pages/twin/sections/EvidenceSections.tsx`, `frontend/src/pages/twin/sections/HistorySection.tsx`, `frontend/src/pages/twin/sections/SkillsSection.tsx`

### `frontend/src/components/ui/overlay.tsx`

* **Purpose:** Radix-based Dialog, ConfirmButton (destructive confirmation) and Tabs.
* **Size:** 140 lines · **Status:** Active — Imported by 11 file(s).
* **Key symbols:** `Dialog` (function) L9, `ConfirmButton` (function) L57, `Tabs` (function) L108, `TabPanel` (const) L140
* **Imports (repository):** `frontend/src/components/ui/button.tsx`, `frontend/src/lib/utils.ts`
* **Imports (third-party/stdlib):** `lucide-react`, `radix-ui`, `react`
* **Imported by:** `frontend/src/components/FeedbackButton.tsx`, `frontend/src/pages/admin/AdminPage.tsx`, `frontend/src/pages/documents/DocumentsPage.tsx`, `frontend/src/pages/mentor/MentorPage.tsx`, `frontend/src/pages/roles/RolesPage.tsx`, `frontend/src/pages/settings/SettingsPage.tsx`, `frontend/src/pages/simulator/SimulatorPage.tsx`, `frontend/src/pages/staff/StaffPage.tsx`, `frontend/src/pages/twin/ProfilePage.tsx`, `frontend/src/pages/twin/sections/AssessmentsSection.tsx`, `frontend/src/pages/twin/sections/EvidenceSections.tsx`

### `frontend/src/components/ui/primitives.tsx`

* **Purpose:** Card, Badge, status/verification badges, hints, level meter, meters, stats, keyboard hints.
* **Size:** 186 lines · **Status:** Active — Imported by 21 file(s).
* **Key symbols:** `Card` (function) L7, `CardHeader` (function) L11, `CardBody` (function) L36, `Tone` (type) L49, `Badge` (function) L51, `StatusBadge` (function) L65, `VerificationBadge` (function) L76, `Hint` (function) L81, `InfoHint` (function) L100, `LevelMeter` (function) L111, `Meter` (function) L154, `Stat` (function) L171, `Kbd` (function) L184
* **Imports (repository):** `frontend/src/lib/utils.ts`
* **Imports (third-party/stdlib):** `lucide-react`, `radix-ui`, `react`
* **Imported by:** `frontend/src/components/components.test.tsx`, `frontend/src/pages/admin/AdminPage.tsx`, `frontend/src/pages/dashboard/DashboardPage.tsx`, `frontend/src/pages/documents/DocumentsPage.tsx`, `frontend/src/pages/gaps/SkillGapsPage.tsx`, `frontend/src/pages/graph/GraphPage.tsx`, `frontend/src/pages/mentor/MentorPage.tsx`, `frontend/src/pages/onboarding/OnboardingPage.tsx`, `frontend/src/pages/progress/ProgressPage.tsx`, `frontend/src/pages/readiness/ModelCardPage.tsx`, `frontend/src/pages/readiness/ReadinessPage.tsx`, `frontend/src/pages/roadmap/RoadmapPage.tsx`, `frontend/src/pages/roles/RolesPage.tsx`, `frontend/src/pages/settings/SettingsPage.tsx`, `frontend/src/pages/simulator/SimulatorPage.tsx`, `frontend/src/pages/staff/StaffPage.tsx`, `frontend/src/pages/twin/sections/AcademicSection.tsx`, `frontend/src/pages/twin/sections/AssessmentsSection.tsx`, `frontend/src/pages/twin/sections/EvidenceSections.tsx`, `frontend/src/pages/twin/sections/HistorySection.tsx`, `frontend/src/pages/twin/sections/SkillsSection.tsx`

### `frontend/src/components/ui/states.tsx`

* **Purpose:** Loading, empty, error (with request id), notice and synthetic-model notice components.
* **Size:** 112 lines · **Status:** Active — Imported by 27 file(s).
* **Key symbols:** `Skeleton` (function) L9, `LoadingBlock` (function) L13, `EmptyState` (function) L24, `ErrorState` (function) L49, `Notice` (function) L73, `SyntheticModelNotice` (function) L104
* **Imports (repository):** `frontend/src/components/ui/button.tsx`, `frontend/src/lib/api.ts`, `frontend/src/lib/utils.ts`
* **Imports (third-party/stdlib):** `lucide-react`, `react`
* **Imported by:** `frontend/src/components/components.test.tsx`, `frontend/src/components/layout/guards.tsx`, `frontend/src/components/twin/TwinVisual.tsx`, `frontend/src/pages/admin/AdminPage.tsx`, `frontend/src/pages/auth/AuthPages.tsx`, `frontend/src/pages/dashboard/DashboardPage.tsx`, `frontend/src/pages/documents/DocumentsPage.tsx`, `frontend/src/pages/errors.tsx`, `frontend/src/pages/gaps/SkillGapsPage.tsx`, `frontend/src/pages/graph/GraphPage.tsx`, `frontend/src/pages/landing/LandingPage.tsx`, `frontend/src/pages/mentor/MentorPage.tsx`, `frontend/src/pages/onboarding/OnboardingPage.tsx`, `frontend/src/pages/progress/ProgressPage.tsx`, `frontend/src/pages/readiness/ModelCardPage.tsx`, `frontend/src/pages/readiness/ReadinessPage.tsx`, `frontend/src/pages/roadmap/RoadmapPage.tsx`, `frontend/src/pages/roles/RolesPage.tsx`, `frontend/src/pages/settings/SettingsPage.tsx`, `frontend/src/pages/simulator/SimulatorPage.tsx`, `frontend/src/pages/staff/StaffPage.tsx`, `frontend/src/pages/twin/sections/AcademicSection.tsx`, `frontend/src/pages/twin/sections/AssessmentsSection.tsx`, `frontend/src/pages/twin/sections/EvidenceSections.tsx`, `frontend/src/pages/twin/sections/HistorySection.tsx`, `frontend/src/pages/twin/sections/SkillsSection.tsx`, `frontend/src/router.tsx`

## Frontend — pages (25 files)

### `frontend/src/pages/admin/AdminPage.tsx`

* **Purpose:** Admin console: system, feedback, users, mentor links, roles, resources, models, knowledge base, audit log.
* **Size:** 405 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `AdminPage` (function) L382
* **Imports (repository):** `frontend/src/components/FeedbackButton.tsx`, `frontend/src/components/layout/AppShell.tsx`, `frontend/src/components/ui/button.tsx`, `frontend/src/components/ui/form.tsx`, `frontend/src/components/ui/overlay.tsx`, `frontend/src/components/ui/primitives.tsx`, `frontend/src/components/ui/states.tsx`, `frontend/src/lib/api.ts`, `frontend/src/lib/queries.ts`, `frontend/src/lib/types.ts`, `frontend/src/lib/utils.ts`
* **Imports (third-party/stdlib):** `@tanstack/react-query`, `lucide-react`, `react`, `sonner`
* **Imported by:** `frontend/src/router.tsx`

### `frontend/src/pages/auth/AuthPages.tsx`

* **Purpose:** Login (+MFA step), registration with consent and password checklist, forgot/reset password, email verification.
* **Size:** 319 lines · **Status:** Active — Imported by 2 file(s).
* **Key symbols:** `LoginPage` (function) L54, `RegisterPage` (function) L150, `ForgotPasswordPage` (function) L220, `ResetPasswordPage` (function) L250, `VerifyEmailPage` (function) L294
* **Imports (repository):** `frontend/src/components/PasswordChecklist.tsx`, `frontend/src/components/layout/Brand.tsx`, `frontend/src/components/ui/button.tsx`, `frontend/src/components/ui/form.tsx`, `frontend/src/components/ui/states.tsx`, `frontend/src/lib/api.ts`, `frontend/src/lib/queries.ts`, `frontend/src/lib/types.ts`
* **Imports (third-party/stdlib):** `@hookform/resolvers`, `@tanstack/react-query`, `lucide-react`, `motion`, `react`, `react-hook-form`, `react-router`, `sonner`, `zod`
* **Imported by:** `frontend/src/pages/auth/auth.test.tsx`, `frontend/src/router.tsx`

### `frontend/src/pages/auth/auth.test.tsx`

* **Purpose:** 6 tests for auth pages (validation, neutral responses, MFA step, accessibility).
* **Size:** 70 lines · **Status:** Active (test) — Collected by the test runner; all tests passed in this audit (2026-10-21).
* **Key symbols:** —
* **Imports (repository):** `frontend/src/pages/auth/AuthPages.tsx`, `frontend/src/test/utils.tsx`
* **Imports (third-party/stdlib):** `@testing-library/react`, `@testing-library/user-event`, `vitest`
* **Imported by:** —

### `frontend/src/pages/dashboard/DashboardPage.tsx`

* **Purpose:** Dashboard: twin visual, completeness, readiness, target-role gaps, learning plan, mentor status, history, next actions.
* **Size:** 222 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `DashboardPage` (function) L85
* **Imports (repository):** `frontend/src/components/charts/Ring.tsx`, `frontend/src/components/layout/AppShell.tsx`, `frontend/src/components/motion.tsx`, `frontend/src/components/twin/TwinVisual.tsx`, `frontend/src/components/ui/button.tsx`, `frontend/src/components/ui/primitives.tsx`, `frontend/src/components/ui/states.tsx`, `frontend/src/lib/api.ts`, `frontend/src/lib/queries.ts`, `frontend/src/lib/types.ts`, `frontend/src/lib/utils.ts`
* **Imports (third-party/stdlib):** `@tanstack/react-query`, `lucide-react`, `react-router`, `sonner`
* **Imported by:** `frontend/src/router.tsx`

### `frontend/src/pages/documents/DocumentsPage.tsx`

* **Purpose:** Resume upload/analysis, job descriptions, skill confirmation and resume-vs-JD comparison.
* **Size:** 219 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `DocumentsPage` (function) L114
* **Imports (repository):** `frontend/src/components/layout/AppShell.tsx`, `frontend/src/components/ui/button.tsx`, `frontend/src/components/ui/form.tsx`, `frontend/src/components/ui/overlay.tsx`, `frontend/src/components/ui/primitives.tsx`, `frontend/src/components/ui/states.tsx`, `frontend/src/lib/api.ts`, `frontend/src/lib/queries.ts`, `frontend/src/lib/types.ts`, `frontend/src/lib/utils.ts`
* **Imports (third-party/stdlib):** `@tanstack/react-query`, `lucide-react`, `react`, `sonner`
* **Imported by:** `frontend/src/router.tsx`

### `frontend/src/pages/errors.tsx`

* **Purpose:** Route error, 404 and 403 pages.
* **Size:** 58 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `NotFoundPage` (function) L18, `ForbiddenPage` (function) L36, `RouteErrorPage` (function) L47
* **Imports (repository):** `frontend/src/components/layout/Brand.tsx`, `frontend/src/components/ui/button.tsx`, `frontend/src/components/ui/states.tsx`
* **Imports (third-party/stdlib):** `lucide-react`, `react-router`
* **Imported by:** `frontend/src/router.tsx`

### `frontend/src/pages/gaps/SkillGapsPage.tsx`

* **Purpose:** Skill-gap analysis per role with adjustable formula parameters and skill-by-skill breakdown.
* **Size:** 201 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `SkillGapsPage` (function) L78
* **Imports (repository):** `frontend/src/components/layout/AppShell.tsx`, `frontend/src/components/ui/button.tsx`, `frontend/src/components/ui/form.tsx`, `frontend/src/components/ui/primitives.tsx`, `frontend/src/components/ui/states.tsx`, `frontend/src/lib/queries.ts`, `frontend/src/lib/types.ts`, `frontend/src/lib/utils.ts`
* **Imports (third-party/stdlib):** `lucide-react`, `motion`, `react`, `recharts`
* **Imported by:** `frontend/src/router.tsx`

### `frontend/src/pages/graph/GraphPage.tsx`

* **Purpose:** Knowledge graph (3D or accessible 2D) and graph insights.
* **Size:** 192 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `GraphPage` (function) L40
* **Imports (repository):** `frontend/src/components/layout/AppShell.tsx`, `frontend/src/components/three/Graph2D.tsx`, `frontend/src/components/three/Graph3D.tsx`, `frontend/src/components/three/graphStyle.ts`, `frontend/src/components/ui/button.tsx`, `frontend/src/components/ui/form.tsx`, `frontend/src/components/ui/primitives.tsx`, `frontend/src/components/ui/states.tsx`, `frontend/src/lib/api.ts`, `frontend/src/lib/queries.ts`, `frontend/src/lib/types.ts`, `frontend/src/lib/utils.ts`, `frontend/src/lib/visuals.ts`
* **Imports (third-party/stdlib):** `@tanstack/react-query`, `lucide-react`, `react`
* **Imported by:** `frontend/src/router.tsx`

### `frontend/src/pages/landing/LandingPage.tsx`

* **Purpose:** Public landing page explaining the product, evidence trust levels and limitations; shows live model info.
* **Size:** 276 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `LandingPage` (function) L105
* **Imports (repository):** `frontend/src/components/layout/Brand.tsx`, `frontend/src/components/motion.tsx`, `frontend/src/components/three/ConstellationFallback.tsx`, `frontend/src/components/three/SkillConstellation.tsx`, `frontend/src/components/ui/button.tsx`, `frontend/src/components/ui/states.tsx`, `frontend/src/lib/api.ts`, `frontend/src/lib/queries.ts`, `frontend/src/lib/visuals.ts`
* **Imports (third-party/stdlib):** `@tanstack/react-query`, `lucide-react`, `motion`, `react`, `react-router`
* **Imported by:** `frontend/src/router.tsx`

### `frontend/src/pages/mentor/MentorPage.tsx`

* **Purpose:** Personalized Mentor chat with streaming, sources, unverified-number and removed-link notices, conversations, answer ratings.
* **Size:** 235 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `MentorPage` (function) L107
* **Imports (repository):** `frontend/src/components/SafeMarkdown.tsx`, `frontend/src/components/layout/AppShell.tsx`, `frontend/src/components/ui/button.tsx`, `frontend/src/components/ui/form.tsx`, `frontend/src/components/ui/overlay.tsx`, `frontend/src/components/ui/primitives.tsx`, `frontend/src/components/ui/states.tsx`, `frontend/src/lib/api.ts`, `frontend/src/lib/queries.ts`, `frontend/src/lib/sse.ts`, `frontend/src/lib/types.ts`, `frontend/src/lib/utils.ts`
* **Imports (third-party/stdlib):** `@tanstack/react-query`, `lucide-react`, `motion`, `react`, `sonner`
* **Imported by:** `frontend/src/router.tsx`

### `frontend/src/pages/onboarding/OnboardingPage.tsx`

* **Purpose:** Four-step onboarding: academics, goals/target role, quick skill self-assessment, availability.
* **Size:** 335 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `OnboardingPage` (function) L287
* **Imports (repository):** `frontend/src/components/layout/Brand.tsx`, `frontend/src/components/ui/button.tsx`, `frontend/src/components/ui/form.tsx`, `frontend/src/components/ui/primitives.tsx`, `frontend/src/components/ui/states.tsx`, `frontend/src/lib/api.ts`, `frontend/src/lib/queries.ts`, `frontend/src/lib/types.ts`, `frontend/src/lib/utils.ts`
* **Imports (third-party/stdlib):** `@hookform/resolvers`, `@tanstack/react-query`, `lucide-react`, `motion`, `react`, `react-hook-form`, `react-router`, `sonner`, `zod`
* **Imported by:** `frontend/src/router.tsx`

### `frontend/src/pages/progress/ProgressPage.tsx`

* **Purpose:** Longitudinal progress: readiness over time, skill trajectory by version, roadmap activity.
* **Size:** 106 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `ProgressPage` (function) L24
* **Imports (repository):** `frontend/src/components/layout/AppShell.tsx`, `frontend/src/components/ui/form.tsx`, `frontend/src/components/ui/primitives.tsx`, `frontend/src/components/ui/states.tsx`, `frontend/src/lib/api.ts`, `frontend/src/lib/queries.ts`, `frontend/src/lib/utils.ts`
* **Imports (third-party/stdlib):** `@tanstack/react-query`, `lucide-react`, `react`, `recharts`
* **Imported by:** `frontend/src/router.tsx`

### `frontend/src/pages/readiness/ModelCardPage.tsx`

* **Purpose:** In-app model card rendered from the active model's manifest.
* **Size:** 168 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `ModelCardPage` (function) L35
* **Imports (repository):** `frontend/src/components/layout/AppShell.tsx`, `frontend/src/components/ui/primitives.tsx`, `frontend/src/components/ui/states.tsx`, `frontend/src/lib/api.ts`, `frontend/src/lib/utils.ts`
* **Imports (third-party/stdlib):** `@tanstack/react-query`, `lucide-react`, `recharts`
* **Imported by:** `frontend/src/router.tsx`

### `frontend/src/pages/readiness/ReadinessPage.tsx`

* **Purpose:** Readiness estimate, warnings, SHAP explanation, history.
* **Size:** 207 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `ReadinessPage` (function) L87
* **Imports (repository):** `frontend/src/components/charts/ShapChart.tsx`, `frontend/src/components/layout/AppShell.tsx`, `frontend/src/components/motion.tsx`, `frontend/src/components/ui/button.tsx`, `frontend/src/components/ui/primitives.tsx`, `frontend/src/components/ui/states.tsx`, `frontend/src/lib/api.ts`, `frontend/src/lib/queries.ts`, `frontend/src/lib/types.ts`, `frontend/src/lib/utils.ts`
* **Imports (third-party/stdlib):** `@tanstack/react-query`, `lucide-react`, `motion`, `react`, `react-router`, `sonner`
* **Imported by:** `frontend/src/router.tsx`

### `frontend/src/pages/roadmap/RoadmapPage.tsx`

* **Purpose:** Personalised roadmap: items, progress, reordering, regeneration, plan history and diff, item feedback.
* **Size:** 236 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `RoadmapPage` (function) L110
* **Imports (repository):** `frontend/src/components/layout/AppShell.tsx`, `frontend/src/components/ui/button.tsx`, `frontend/src/components/ui/form.tsx`, `frontend/src/components/ui/primitives.tsx`, `frontend/src/components/ui/states.tsx`, `frontend/src/lib/api.ts`, `frontend/src/lib/queries.ts`, `frontend/src/lib/types.ts`, `frontend/src/lib/utils.ts`
* **Imports (third-party/stdlib):** `@tanstack/react-query`, `lucide-react`, `motion`, `react`, `sonner`
* **Imported by:** `frontend/src/router.tsx`

### `frontend/src/pages/roles/RolesPage.tsx`

* **Purpose:** Role explorer with match ranking, framework provenance and ranking sensitivity.
* **Size:** 144 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `RolesPage` (function) L56
* **Imports (repository):** `frontend/src/components/layout/AppShell.tsx`, `frontend/src/components/motion.tsx`, `frontend/src/components/ui/button.tsx`, `frontend/src/components/ui/overlay.tsx`, `frontend/src/components/ui/primitives.tsx`, `frontend/src/components/ui/states.tsx`, `frontend/src/lib/api.ts`, `frontend/src/lib/queries.ts`, `frontend/src/lib/types.ts`, `frontend/src/lib/utils.ts`
* **Imports (third-party/stdlib):** `@tanstack/react-query`, `lucide-react`, `react`, `sonner`
* **Imported by:** `frontend/src/router.tsx`

### `frontend/src/pages/settings/SettingsPage.tsx`

* **Purpose:** Account, password, MFA, sessions, consents, export, deletion and display preferences.
* **Size:** 223 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `SettingsPage` (function) L202
* **Imports (repository):** `frontend/src/components/PasswordChecklist.tsx`, `frontend/src/components/layout/AppShell.tsx`, `frontend/src/components/ui/button.tsx`, `frontend/src/components/ui/form.tsx`, `frontend/src/components/ui/overlay.tsx`, `frontend/src/components/ui/primitives.tsx`, `frontend/src/components/ui/states.tsx`, `frontend/src/lib/api.ts`, `frontend/src/lib/queries.ts`, `frontend/src/lib/utils.ts`, `frontend/src/lib/visuals.ts`
* **Imports (third-party/stdlib):** `@tanstack/react-query`, `lucide-react`, `react`, `react-router`, `sonner`
* **Imported by:** `frontend/src/router.tsx`

### `frontend/src/pages/simulator/SimulatorPage.tsx`

* **Purpose:** What-if simulator: hypothetical inputs, readiness and role-match comparison, saved scenarios.
* **Size:** 320 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `SimulatorPage` (function) L95
* **Imports (repository):** `frontend/src/components/layout/AppShell.tsx`, `frontend/src/components/ui/button.tsx`, `frontend/src/components/ui/form.tsx`, `frontend/src/components/ui/overlay.tsx`, `frontend/src/components/ui/primitives.tsx`, `frontend/src/components/ui/states.tsx`, `frontend/src/lib/api.ts`, `frontend/src/lib/queries.ts`, `frontend/src/lib/utils.ts`
* **Imports (third-party/stdlib):** `@tanstack/react-query`, `lucide-react`, `motion`, `react`, `recharts`, `sonner`
* **Imported by:** `frontend/src/router.tsx`

### `frontend/src/pages/staff/StaffPage.tsx`

* **Purpose:** Mentor tools: student selection, overview, verification, recorded assessments, readiness labels, queue.
* **Size:** 185 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `StaffPage` (function) L142
* **Imports (repository):** `frontend/src/components/layout/AppShell.tsx`, `frontend/src/components/ui/button.tsx`, `frontend/src/components/ui/form.tsx`, `frontend/src/components/ui/overlay.tsx`, `frontend/src/components/ui/primitives.tsx`, `frontend/src/components/ui/states.tsx`, `frontend/src/lib/api.ts`, `frontend/src/lib/utils.ts`
* **Imports (third-party/stdlib):** `@tanstack/react-query`, `lucide-react`, `react`, `sonner`
* **Imported by:** `frontend/src/router.tsx`

### `frontend/src/pages/twin/ProfilePage.tsx`

* **Purpose:** Twin profile page composing the section components.
* **Size:** 51 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `ProfilePage` (function) L14
* **Imports (repository):** `frontend/src/components/layout/AppShell.tsx`, `frontend/src/components/ui/overlay.tsx`, `frontend/src/lib/queries.ts`, `frontend/src/pages/twin/sections/AcademicSection.tsx`, `frontend/src/pages/twin/sections/AssessmentsSection.tsx`, `frontend/src/pages/twin/sections/EvidenceSections.tsx`, `frontend/src/pages/twin/sections/HistorySection.tsx`, `frontend/src/pages/twin/sections/SkillsSection.tsx`
* **Imports (third-party/stdlib):** `lucide-react`, `react-router`
* **Imported by:** `frontend/src/router.tsx`

### `frontend/src/pages/twin/sections/AcademicSection.tsx`

* **Purpose:** Academic information form.
* **Size:** 84 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `AcademicSection` (function) L29
* **Imports (repository):** `frontend/src/components/ui/button.tsx`, `frontend/src/components/ui/form.tsx`, `frontend/src/components/ui/primitives.tsx`, `frontend/src/components/ui/states.tsx`, `frontend/src/lib/api.ts`, `frontend/src/lib/queries.ts`
* **Imports (third-party/stdlib):** `@hookform/resolvers`, `react`, `react-hook-form`, `react-router`, `sonner`, `zod`
* **Imported by:** `frontend/src/pages/twin/ProfilePage.tsx`

### `frontend/src/pages/twin/sections/AssessmentsSection.tsx`

* **Purpose:** Assessment results list and self-reported result form.
* **Size:** 113 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `AssessmentsSection` (function) L14
* **Imports (repository):** `frontend/src/components/ui/button.tsx`, `frontend/src/components/ui/form.tsx`, `frontend/src/components/ui/overlay.tsx`, `frontend/src/components/ui/primitives.tsx`, `frontend/src/components/ui/states.tsx`, `frontend/src/lib/api.ts`, `frontend/src/lib/queries.ts`, `frontend/src/lib/utils.ts`
* **Imports (third-party/stdlib):** `lucide-react`, `react`, `sonner`
* **Imported by:** `frontend/src/pages/twin/ProfilePage.tsx`

### `frontend/src/pages/twin/sections/EvidenceSections.tsx`

* **Purpose:** Projects, experience and certifications with skill-evidence links and verification requests.
* **Size:** 374 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `SkillLinksEditor` (function) L20, `ProjectsSection` (function) L147, `ExperienceSection` (function) L253, `CertificationsSection` (function) L310
* **Imports (repository):** `frontend/src/components/ui/button.tsx`, `frontend/src/components/ui/form.tsx`, `frontend/src/components/ui/overlay.tsx`, `frontend/src/components/ui/primitives.tsx`, `frontend/src/components/ui/states.tsx`, `frontend/src/lib/api.ts`, `frontend/src/lib/queries.ts`, `frontend/src/lib/types.ts`, `frontend/src/lib/utils.ts`
* **Imports (third-party/stdlib):** `@hookform/resolvers`, `lucide-react`, `react`, `react-hook-form`, `sonner`, `zod`
* **Imported by:** `frontend/src/pages/twin/ProfilePage.tsx`

### `frontend/src/pages/twin/sections/HistorySection.tsx`

* **Purpose:** Snapshot versions and human-readable diffs.
* **Size:** 99 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `HistorySection` (function) L31
* **Imports (repository):** `frontend/src/components/ui/form.tsx`, `frontend/src/components/ui/primitives.tsx`, `frontend/src/components/ui/states.tsx`, `frontend/src/lib/api.ts`, `frontend/src/lib/queries.ts`, `frontend/src/lib/utils.ts`
* **Imports (third-party/stdlib):** `@tanstack/react-query`, `lucide-react`, `react`
* **Imported by:** `frontend/src/pages/twin/ProfilePage.tsx`

### `frontend/src/pages/twin/sections/SkillsSection.tsx`

* **Purpose:** Skill ratings with estimates and evidence status.
* **Size:** 140 lines · **Status:** Active — Imported by 1 file(s).
* **Key symbols:** `SkillsSection` (function) L82
* **Imports (repository):** `frontend/src/components/ui/button.tsx`, `frontend/src/components/ui/form.tsx`, `frontend/src/components/ui/primitives.tsx`, `frontend/src/components/ui/states.tsx`, `frontend/src/lib/api.ts`, `frontend/src/lib/queries.ts`, `frontend/src/lib/types.ts`, `frontend/src/lib/utils.ts`
* **Imports (third-party/stdlib):** `lucide-react`, `motion`, `react`, `sonner`
* **Imported by:** `frontend/src/pages/twin/ProfilePage.tsx`

## Infrastructure (6 files)

### `infra/caddy/Caddyfile`

* **Purpose:** Example TLS edge (Caddy) in front of the web container for staging/production.
* **Size:** 18 lines · **Status:** Active (configuration) — Read by the tool named in the purpose.

### `infra/neon/setup.sql`

* **Purpose:** One-time Neon setup: least-privilege `twinpath_app` role (NOBYPASSRLS), guard-rail settings, grants, verification query.
* **Size:** 31 lines · **Status:** Active (configuration) — Read by the tool named in the purpose.

### `infra/postgres/grants.sql`

* **Purpose:** Re-applies runtime grants after a restore (mirrors migration 0002).
* **Size:** 12 lines · **Status:** Active (configuration) — Read by the tool named in the purpose.

### `infra/postgres/init/01-roles-and-databases.sh`

* **Purpose:** First-start bootstrap for the compose database: owner and app roles, database ownership, schema privileges.
* **Size:** 40 lines · **Status:** Active (configuration) — Read by the tool named in the purpose.

### `infra/scripts/backup.sh`

* **Purpose:** Logical backup (`pg_dump -Fc`) from the compose database.
* **Size:** 15 lines · **Status:** Active (configuration) — Read by the tool named in the purpose.

### `infra/scripts/restore-check.sh`

* **Purpose:** Restores the latest backup into a scratch database and compares table row counts.
* **Size:** 34 lines · **Status:** Active (configuration) — Read by the tool named in the purpose.

## Knowledge base (mentor documents) (7 files)

### `knowledge/interview-preparation.md`

* **Purpose:** Mentor knowledge base: interview formats and preparation (no company-specific claims).
* **Size:** 45 lines · **Status:** Active (data) — Indexed into the global vector collection by `reindex_global`.

### `knowledge/learning-strategies.md`

* **Purpose:** Mentor knowledge base: prerequisites, spaced repetition, weekly planning, resource quality.
* **Size:** 33 lines · **Status:** Active (data) — Indexed into the global vector collection by `reindex_global`.

### `knowledge/platform-methodology.md`

* **Purpose:** Mentor knowledge base: how the app's twin, matching, readiness, simulator and mentor work, and their limits.
* **Size:** 50 lines · **Status:** Active (data) — Indexed into the global vector collection by `reindex_global`.

### `knowledge/privacy-and-data-use.md`

* **Purpose:** Mentor knowledge base: data use, access, consent, retention.
* **Size:** 39 lines · **Status:** Active (data) — Indexed into the global vector collection by `reindex_global`.

### `knowledge/proficiency-scale.md`

* **Purpose:** Mentor knowledge base: the 0–4 proficiency scale with examples.
* **Size:** 37 lines · **Status:** Active (data) — Indexed into the global vector collection by `reindex_global`.

### `knowledge/project-planning.md`

* **Purpose:** Mentor knowledge base: planning portfolio projects from skill gaps.
* **Size:** 35 lines · **Status:** Active (data) — Indexed into the global vector collection by `reindex_global`.

### `knowledge/resume-guidelines.md`

* **Purpose:** Mentor knowledge base: credible, honest resume writing.
* **Size:** 35 lines · **Status:** Active (data) — Indexed into the global vector collection by `reindex_global`.

## Documentation (25 files)

### `docs/api/README.md`

* **Purpose:** API conventions (errors, auth, CSRF, pagination) and the endpoint groups with counts.
* **Size:** 35 lines · **Status:** Documentation — Not executed.

### `docs/api/openapi.json`

* **Purpose:** OpenAPI 3.1 specification generated from the code (106 paths, 124 operations).
* **Size:** 7419 lines · **Status:** Generated — Produced by a tool or pipeline run; regenerate rather than edit by hand.

### `docs/architecture.md`

* **Purpose:** Architecture overview: component diagram, backend layering, auth/RLS, data model, ML lifecycle, mentor request path, frontend.
* **Size:** 111 lines · **Status:** Documentation — Not executed.

### `docs/methodology/README.md`

* **Purpose:** Methodology: proficiency estimation, gap formula, simulator, roadmap and knowledge-graph rules.
* **Size:** 82 lines · **Status:** Documentation — Not executed.

### `docs/methodology/role-framework.md`

* **Purpose:** Provenance and design of the role-skill framework v1 and its limitations.
* **Size:** 23 lines · **Status:** Documentation — Not executed.

### `docs/ml/dataset-card.md`

* **Purpose:** Dataset card for the synthetic cohort and the planned real-label sources.
* **Size:** 54 lines · **Status:** Documentation — Not executed.

### `docs/ml/model-card.md`

* **Purpose:** Model card for the active readiness classifier with test metrics and limitations.
* **Size:** 106 lines · **Status:** Documentation — Not executed.

### `docs/operations/backup-restore.md`

* **Purpose:** Backup, verification and disaster-recovery procedures for the compose database.
* **Size:** 49 lines · **Status:** Documentation — Not executed.

### `docs/operations/deployment.md`

* **Purpose:** Environments, LLM topologies, hardware, first deployment, releases/rollback, monitoring.
* **Size:** 77 lines · **Status:** Documentation — Not executed.

### `docs/operations/free-hosting.md`

* **Purpose:** Step-by-step Vercel + Render + Neon free hosting guide with measured limits.
* **Size:** 187 lines · **Status:** Documentation — Not executed.

### `docs/reports/llm-benchmark.json`

* **Purpose:** Measured local LLM benchmark (qwen3:8b on RTX 4060 Laptop: ~5.1 s warm, 42.7 tok/s, 5.3 GB VRAM).
* **Size:** 66 lines · **Status:** Documentation — Not executed.

### `docs/reports/rag-eval-run1-baseline.json`

* **Purpose:** Historical RAG evaluation run 1 (baseline) — raw results.
* **Size:** 543 lines · **Status:** Generated — Produced by a tool or pipeline run; regenerate rather than edit by hand.

### `docs/reports/rag-eval-run1-baseline.md`

* **Purpose:** Historical RAG evaluation run 1 (baseline) — readable report.
* **Size:** 118 lines · **Status:** Generated — Produced by a tool or pipeline run; regenerate rather than edit by hand.

### `docs/reports/rag-eval-run2.json`

* **Purpose:** Historical RAG evaluation run 2 (contextual chunk headers) — raw results.
* **Size:** 511 lines · **Status:** Generated — Produced by a tool or pipeline run; regenerate rather than edit by hand.

### `docs/reports/rag-eval-run3.json`

* **Purpose:** Historical RAG evaluation run 3 — raw results.
* **Size:** 511 lines · **Status:** Generated — Produced by a tool or pipeline run; regenerate rather than edit by hand.

### `docs/reports/rag-eval-run4.json`

* **Purpose:** Historical RAG evaluation run 4 — raw results.
* **Size:** 529 lines · **Status:** Generated — Produced by a tool or pipeline run; regenerate rather than edit by hand.

### `docs/reports/rag-eval.json`

* **Purpose:** Latest RAG evaluation results (regenerated by `eval.run_rag_eval`).
* **Size:** 540 lines · **Status:** Generated — Produced by a tool or pipeline run; regenerate rather than edit by hand.

### `docs/reports/rag-eval.md`

* **Purpose:** Latest RAG evaluation report with every answer for human review.
* **Size:** 122 lines · **Status:** Generated — Produced by a tool or pipeline run; regenerate rather than edit by hand.

### `docs/reports/rag-evaluation.md`

* **Purpose:** Narrative RAG evaluation write-up: method, iterations, limitations.
* **Size:** 47 lines · **Status:** Generated — Produced by a tool or pipeline run; regenerate rather than edit by hand.

### `docs/research.md`

* **Purpose:** Research framing: contribution, research questions, measured vs designed vs simulated, proposed pilot, threats to validity.
* **Size:** 65 lines · **Status:** Documentation — Not executed.

### `docs/security/checklist.md`

* **Purpose:** Built-in security controls and the operator go-live checklist.
* **Size:** 89 lines · **Status:** Documentation — Not executed.

### `docs/security/dependency-exceptions.md`

* **Purpose:** Documented, scoped exceptions for four Chroma HTTP-server advisories.
* **Size:** 26 lines · **Status:** Documentation — Not executed.

### `docs/security/incident-response.md`

* **Purpose:** Incident response procedure.
* **Size:** 33 lines · **Status:** Documentation — Not executed.

### `docs/security/threat-model.md`

* **Purpose:** STRIDE-style threat model T1–T24 with controls and test evidence.
* **Size:** 58 lines · **Status:** Documentation — Not executed.

### `docs/status-and-limitations.md`

* **Purpose:** Definition-of-Done table and known limitations (as of 2026-10-14, updated 2026-10-21).
* **Size:** 91 lines · **Status:** Documentation — Not executed.

## Totals

| Section | Files |
|---|---|
| Root and repository configuration | 9 |
| Backend — configuration, packaging and migrations | 8 |
| Backend — application core (`backend/app/*.py`) | 9 |
| Backend — HTTP API (`backend/app/api`) | 12 |
| Backend — schemas and security | 9 |
| Backend — database models | 6 |
| Backend — machine learning (runtime) | 5 |
| Backend — reference data seeding | 3 |
| Backend — services | 28 |
| Backend — ML training pipeline | 6 |
| Backend — model artifacts | 11 |
| Backend — RAG evaluation | 3 |
| Backend — scripts | 2 |
| Backend — tests | 10 |
| Frontend — configuration and tooling | 15 |
| Frontend — application core and libraries | 13 |
| Frontend — components | 26 |
| Frontend — pages | 25 |
| Infrastructure | 6 |
| Knowledge base (mentor documents) | 7 |
| Documentation | 25 |
| **Total** | **238** |
