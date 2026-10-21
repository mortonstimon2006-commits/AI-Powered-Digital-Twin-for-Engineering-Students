# 03 — Backend code walkthrough

The backend is a Python 3.12 FastAPI application in `backend/`. It is organised in layers:

* `app/api/v1` — HTTP routers;
* `app/services` — business logic;
* `app/models` — SQLAlchemy ORM;
* `app/ml` — runtime ML;
* `app/security`, `app/schemas`, `app/seed`;
* `ml_pipeline`, `eval`, `tests` — offline tooling and tests.

This chapter follows a request through the stack, then explains each module. Deep dives on the career engine, ML,
RAG and documents are in chapters 05–09 and 14.

## 1. From HTTP request to response

The concrete example used below is `POST /api/v1/twin/projects` (create a project with skill evidence).

1. **uvicorn** receives the request and calls the ASGI app built by `create_app()`
   (`backend/app/main.py` L35–60).
2. **CORS** (`main.py` L51–58) is the outermost middleware: Starlette runs the last-added middleware first. It only
   accepts the configured origins, the methods GET/POST/PUT/PATCH/DELETE and the headers `content-type`,
   `x-csrf-token` and `x-requested-with`.
3. **`SecurityMiddleware`** (`backend/app/middleware.py` L52–140):
   * gives the request a random `request_id` (L65–66);
   * for unsafe methods on `/api/*`, rejects with **403** if an `Origin` header is present and isn't in
     `ALLOWED_ORIGINS`, or if `X-Requested-With: twinpath` is missing (L74–83);
   * rejects bodies larger than `MAX_UPLOAD_MB` + 64 KiB, by declared length and while streaming (L85–103, **413**);
   * adds the security headers to every response: `nosniff`, `DENY` framing, `no-referrer`, COOP/CORP,
     `Permissions-Policy`, `Cache-Control: no-store`, CSP `default-src 'none'`, and HSTS in staging/production
     (L107–121);
   * writes one JSON access-log line (L132–140).
4. **Routing**: `api_router` (`backend/app/api/v1/__init__.py`) is mounted at `/api/v1` (`main.py` L59), and FastAPI
   selects `twin.create_project`.
5. **Validation**: the body is parsed into `ProjectIn` (`backend/app/schemas/twin.py` L110). Every request model
   derives from `StrictModel` (`backend/app/schemas/common.py` L6–9: `extra="forbid"`, whitespace stripped):
   * unknown fields are rejected;
   * URLs must be `https://` (`_https_url`, L17);
   * lengths and ranges are bounded.

   A failure becomes **422** `validation_error` with field details (`backend/app/errors.py` L84–94).
6. **Dependencies** (`backend/app/deps.py`):
   * `get_db` (`backend/app/db.py` L90–100) opens a session.
   * `get_principal` (L79–87) runs `_load_session` (L50–70). That reads the session cookie (≤128 characters), looks
     up `user_sessions.token_hash = SHA-256(cookie)` with `revoked_at IS NULL`, and enforces absolute expiry, the
     idle limit and `is_active`. `last_seen_at` is refreshed at most every 5 minutes.
   * For unsafe methods, `_verify_csrf` (L73–76) compares `SHA-256(X-CSRF-Token)` with the stored `csrf_hash` in
     constant time and raises **403** `csrf_invalid` on mismatch.
   * Finally `set_rls_subject(db, user.id)` (`db.py` L61–66): from now on every transaction in this request runs
     `set_config('app.user_id', <id>, true)` (`db.py` L52–58), so PostgreSQL row-level security only exposes this
     user's rows.
7. **Handler logic**: `create_project` inserts the `projects` row with `user_id = principal.id` (never a client-sent
   id). It then calls `_replace_evidence` (`twin.py` L255–277), which validates skill ids, rejects duplicates and
   writes `skill_evidence` rows.
8. **Snapshot and commit**: `_commit_change` (`twin.py` L97–99) calls `ensure_snapshot`
   (`backend/app/services/twin/history.py` L18–40). A new `twin_snapshots` row is written only if the twin's content
   hash changed. Then `db.commit()`. Endpoints always commit explicitly; anything left uncommitted is rolled back by
   `get_db` (L98–99), never silently committed.
9. **Response**: the handler returns a Pydantic response model (`ProjectOut`), and FastAPI serialises it to JSON.
10. **Errors anywhere** become the uniform envelope `{"error": {"code", "message", "details"?, "request_id"}}`
    (`errors.py` L69–117):
    * `AppError` subclasses map to 400/401/403/404/409/429/503;
    * `IntegrityError` → 409;
    * `OperationalError` → 503;
    * anything else → a generic 500 with no stack trace.

## 2. Startup lifecycle

`create_app()` (`main.py` L35–60):

1. `configure_logging(settings.log_level)` installs the JSON formatter with redaction
   (`backend/app/logging_config.py` L58–67).
2. Creates FastAPI with `debug=False` always. Interactive docs (`/api/docs`) are enabled only when
   `enable_api_docs` is true, or by default outside staging/production (`config.py` L118–122).
3. Installs the error handlers and both middlewares, and mounts the router.

`lifespan` (`main.py` L21–32) runs once at startup:

* creates `DATA_DIR/uploads`, `chroma` and `outbox`;
* calls `registry.warm()` (`backend/app/ml/registry.py` L104–122), which loads the single active
  `readiness_classifier` from `model_versions` and verifies it (§6). If that fails, the API still starts and
  readiness reports *unavailable*.

`get_settings()` is `lru_cache`d. `Settings` (`backend/app/config.py` L34–155) reads environment variables and the
repository `.env`. Its validator `_fail_closed_in_production` (L137–155) refuses to start when:

* `SECRET_KEY` is under 32 characters; or
* in staging/production: cookies aren't Secure, any origin isn't `https://`, the e-mail backend is `file`,
  verification is required without SMTP, or the database URL still contains `change-me`.

## 3. Cross-cutting modules

| Module | Responsibility | Key functions (lines) | Notes |
|---|---|---|---|
| `app/config.py` | Typed settings | `Settings` L34, `_use_psycopg_driver` L99–108, `_fail_closed_in_production` L137–155 | Cookie names gain the `__Host-` prefix when `COOKIE_SECURE=true` (L124–131) |
| `app/db.py` | Engine, sessions, RLS scope | `get_engine` L30–44 (pool or `NullPool` when `DB_DISABLE_POOL`), `_apply_rls_scope` L52–58, `set_rls_subject` L61–66, `privileged_scope` L69–82, `get_db` L90–100, `system_session` L103–116 | `privileged_scope` lifts RLS only for code paths already authorised in Python (admin catalogue edits, consent lookups by mentors, retention) |
| `app/deps.py` | Auth dependencies | `client_ip` L38–43 (trusts `X-Forwarded-For` only if `TRUST_PROXY_HEADERS`), `get_principal` L79–87, `get_optional_principal` L90–94, `require_roles` L97–103 | Typed aliases L106–110 used in every router signature |
| `app/errors.py` | Error envelope | `AppError` L21, `TooManyRequests` L55 (adds `Retry-After`), handlers L78–117 | |
| `app/middleware.py` | Request-level security | `SecurityMiddleware.__call__` L60–130 | Pure ASGI (no `BaseHTTPMiddleware`), so streaming responses aren't buffered |
| `app/logging_config.py` | JSON logs | `redact` L24–33 (masks keys like password/token/cookie/session/prompt/content), `JsonFormatter` L36–55 | Uvicorn's URL access log is disabled (query strings could hold tokens) |
| `app/services/audit.py` | Audit trail | `record` L18–41 (same transaction), `record_standalone` L44–57 (own transaction, for failures that roll back) | The app role can only INSERT/SELECT `audit_events` (migration 0002) |
| `app/services/email.py` | E-mail | `send_email` L21–45; templates L48–84 | `file` (dev outbox), `smtp` (STARTTLS), `none`. Sent via FastAPI `BackgroundTasks` after the response |

### Background work

There is **no scheduler or worker process**. The only deferred work is e-mail sending through FastAPI
`BackgroundTasks` (`auth.py` L101–104), which runs in the same process after the response is sent. Retention is run
on demand (`python -m app.cli retention` or `POST /api/v1/admin/retention/run`). Knowledge-base indexing is likewise
on demand (`reindex-kb` or the admin button).

## 4. Authentication and authorisation

All in `backend/app/services/auth_service.py` (378 lines) with thin routers in `backend/app/api/v1/auth.py`.

| Flow | Function (lines) | Logic | Tables | Tests |
|---|---|---|---|---|
| Register | `register` L80–108 | Rate limit `REGISTER_IP` (10/h); consent required; `password_problems` (≥12 characters, ≤128, blocklist, not the e-mail or name); **hash before lookup** so both branches cost the same; on a new e-mail insert the user, consent, empty profile and a `verify_email` token digest; audit. The router always returns 202 with the same message and e-mails after the response (`auth.py` L89–105) | users, consents, student_profiles, auth_tokens, audit_events | `test_register_is_non_enumerating_and_sends_mail`, `test_weak_password_and_missing_consent_rejected` |
| Login | `login` L177–229 | Rate limits per IP (20/5 min) and per account (8/5 min); `SELECT … FOR NO KEY UPDATE` serialises failure counting; locked → dummy verify (timing) + standalone audit + generic 401; wrong password → `failed_login_count += 1`, lockout after 5 for 15 min × 2ⁿ (capped at 24 h); success → reset counter, rehash if parameters changed, MFA challenge or new session | users, user_sessions, auth_tokens, audit_events | `test_lockout_after_repeated_failures`, `test_login_rate_limit`, `test_login_errors_do_not_reveal_account_existence` |
| Session | `create_session` L147–160 | 256-bit random token and CSRF token; only their SHA-256 digests are stored; `expires_at = now + SESSION_ABSOLUTE_HOURS` (default 168 h) | user_sessions | `test_credentials_are_stored_only_as_hashes` |
| Cookies | `_set_auth_cookies` (`auth.py` L39–54) | Session cookie HttpOnly + SameSite=Lax + Secure; CSRF cookie readable by JS + SameSite=Strict + Secure; `__Host-` prefix when Secure | — | `test_login_sets_hardened_cookies_and_me_works` |
| MFA login | `login_mfa` L232–251 | Single-use 5-minute challenge token (max 5 attempts); TOTP verified with ±1 step window; secret decrypted with Fernet | auth_tokens, user_sessions | `test_mfa_enrolment_login_and_disable` |
| Password change | `change_password` L290–303 | Verify current password; policy; reject reuse; revoke all other sessions | users, user_sessions | `test_change_password_revokes_other_sessions` |
| Forgot / reset | `request_password_reset` L306–323, `reset_password` L326–341 | Per-IP and per-account limits; invalidates older reset tokens; 30-minute single-use token; reset clears lockout and revokes **all** sessions | auth_tokens, users, user_sessions | `test_password_reset_flow_single_use_and_revokes_sessions`, `test_expired_reset_token_rejected` |
| MFA setup / disable | L347–378 | Secret encrypted with `FIELD_ENCRYPTION_KEY`; enabling requires a valid code; disabling requires password **and** code | users | same MFA test |

**Role-based access control:** roles are `student`, `mentor` and `admin` (CHECK constraint, `models/identity.py`
L65). `require_roles` (`deps.py` L97–103) guards the staff and admin routers. Mentors additionally pass
`_accessible_student` (`staff.py` L44–57): an admin-created `mentor_links` row **and** the student's live
`mentor_sharing` consent are required. Otherwise the response is 404, so a mentor can't tell whether the student
exists, and a denied-access audit event is written.

## 5. Routers

### All 124 API operations

Generated from the route decorators in `backend/app/api/v1/*.py` (counts: 9 public, 4 optional sign-in, 78 signed
in, 7 mentor or admin, 26 admin).

| Method | Path | Handler (file:line) | Access |
|---|---|---|---|
| GET | `/api/v1/admin/system` | `system_status` (`api/v1/admin.py`:55) | Admin |
| POST | `/api/v1/admin/retention/run` | `run_retention` (`api/v1/admin.py`:85) | Admin |
| GET | `/api/v1/admin/audit` | `audit_log` (`api/v1/admin.py`:94) | Admin |
| GET | `/api/v1/admin/feedback` | `feedback_list` (`api/v1/admin.py`:126) | Admin |
| GET | `/api/v1/admin/feedback/summary` | `feedback_summary` (`api/v1/admin.py`:160) | Admin |
| GET | `/api/v1/admin/users` | `list_users` (`api/v1/admin.py`:175) | Admin |
| PATCH | `/api/v1/admin/users/{user_id}` | `patch_user` (`api/v1/admin.py`:217) | Admin |
| GET | `/api/v1/admin/mentor-links` | `list_links` (`api/v1/admin.py`:243) | Admin |
| POST | `/api/v1/admin/mentor-links` | `add_link` (`api/v1/admin.py`:261) | Admin |
| DELETE | `/api/v1/admin/mentor-links/{mentor_id}/{student_id}` | `remove_link` (`api/v1/admin.py`:274) | Admin |
| POST | `/api/v1/admin/roles` | `create_role` (`api/v1/admin.py`:316) | Admin |
| PUT | `/api/v1/admin/roles/{role_id}` | `update_role` (`api/v1/admin.py`:330) | Admin |
| DELETE | `/api/v1/admin/roles/{role_id}` | `deactivate_role` (`api/v1/admin.py`:349) | Admin |
| POST | `/api/v1/admin/skills` | `create_skill` (`api/v1/admin.py`:371) | Admin |
| PUT | `/api/v1/admin/skills/{skill_id}/prerequisites` | `set_prerequisites` (`api/v1/admin.py`:390) | Admin |
| GET | `/api/v1/admin/resources` | `list_resources` (`api/v1/admin.py`:426) | Admin |
| POST | `/api/v1/admin/resources` | `create_resource` (`api/v1/admin.py`:452) | Admin |
| DELETE | `/api/v1/admin/resources/{resource_id}` | `deactivate_resource` (`api/v1/admin.py`:472) | Admin |
| POST | `/api/v1/admin/resources/validate` | `validate_links` (`api/v1/admin.py`:487) | Admin |
| GET | `/api/v1/admin/models` | `list_models` (`api/v1/admin.py`:498) | Admin |
| POST | `/api/v1/admin/models/{model_id}/activate` | `activate_model` (`api/v1/admin.py`:520) | Admin |
| POST | `/api/v1/admin/models/{model_id}/retire` | `retire_model` (`api/v1/admin.py`:540) | Admin |
| GET | `/api/v1/admin/knowledge` | `list_knowledge` (`api/v1/admin.py`:555) | Admin |
| POST | `/api/v1/admin/knowledge/reindex` | `reindex` (`api/v1/admin.py`:576) | Admin |
| POST | `/api/v1/admin/knowledge/upload` | `upload_knowledge` (`api/v1/admin.py`:592) | Admin |
| DELETE | `/api/v1/admin/knowledge/{doc_id}` | `delete_knowledge` (`api/v1/admin.py`:630) | Admin |
| POST | `/api/v1/auth/register` | `register` (`api/v1/auth.py`:89) | Public |
| POST | `/api/v1/auth/login` | `login` (`api/v1/auth.py`:108) | Public |
| POST | `/api/v1/auth/login/mfa` | `login_mfa` (`api/v1/auth.py`:125) | Public |
| POST | `/api/v1/auth/logout` | `logout` (`api/v1/auth.py`:140) | Signed in |
| GET | `/api/v1/auth/me` | `me` (`api/v1/auth.py`:147) | Signed in |
| GET | `/api/v1/auth/csrf` | `refresh_csrf` (`api/v1/auth.py`:152) | Signed in |
| GET | `/api/v1/auth/sessions` | `sessions` (`api/v1/auth.py`:169) | Signed in |
| DELETE | `/api/v1/auth/sessions/{session_id}` | `revoke_session` (`api/v1/auth.py`:185) | Signed in |
| POST | `/api/v1/auth/sessions/revoke-others` | `revoke_other_sessions` (`api/v1/auth.py`:191) | Signed in |
| POST | `/api/v1/auth/password/change` | `change_password` (`api/v1/auth.py`:198) | Signed in |
| POST | `/api/v1/auth/password/forgot` | `forgot_password` (`api/v1/auth.py`:214) | Public |
| POST | `/api/v1/auth/password/reset` | `reset_password` (`api/v1/auth.py`:224) | Public |
| POST | `/api/v1/auth/email/verify` | `verify_email` (`api/v1/auth.py`:233) | Public |
| POST | `/api/v1/auth/email/resend` | `resend_verification` (`api/v1/auth.py`:239) | Signed in |
| POST | `/api/v1/auth/mfa/setup` | `mfa_setup` (`api/v1/auth.py`:247) | Signed in |
| POST | `/api/v1/auth/mfa/verify` | `mfa_verify` (`api/v1/auth.py`:253) | Signed in |
| POST | `/api/v1/auth/mfa/disable` | `mfa_disable` (`api/v1/auth.py`:259) | Signed in |
| GET | `/api/v1/roles` | `list_roles` (`api/v1/career.py`:60) | Optional sign-in |
| GET | `/api/v1/roles/{role_id}` | `get_role` (`api/v1/career.py`:71) | Optional sign-in |
| GET | `/api/v1/catalogue/skills` | `list_catalogue_skills` (`api/v1/career.py`:80) | Optional sign-in |
| GET | `/api/v1/readiness/model` | `readiness_model_info` (`api/v1/career.py`:102) | Optional sign-in |
| POST | `/api/v1/readiness/analyse` | `run_readiness` (`api/v1/career.py`:145) | Signed in |
| GET | `/api/v1/readiness/latest` | `latest_readiness` (`api/v1/career.py`:166) | Signed in |
| GET | `/api/v1/readiness/history` | `readiness_history` (`api/v1/career.py`:192) | Signed in |
| GET | `/api/v1/skill-gaps/roles/{role_id}` | `role_gap_analysis` (`api/v1/career.py`:222) | Signed in |
| GET | `/api/v1/skill-gaps/summary` | `role_matches` (`api/v1/career.py`:264) | Signed in |
| GET | `/api/v1/skill-gaps/sensitivity` | `role_ranking_sensitivity` (`api/v1/career.py`:288) | Signed in |
| POST | `/api/v1/simulations/run` | `run_simulation` (`api/v1/career.py`:303) | Signed in |
| POST | `/api/v1/simulations/scenarios` | `save_scenario` (`api/v1/career.py`:314) | Signed in |
| GET | `/api/v1/simulations/scenarios` | `list_scenarios` (`api/v1/career.py`:337) | Signed in |
| DELETE | `/api/v1/simulations/scenarios/{scenario_id}` | `delete_scenario` (`api/v1/career.py`:349) | Signed in |
| GET | `/api/v1/twin/features` | `current_features` (`api/v1/career.py`:359) | Signed in |
| GET | `/api/v1/documents` | `list_documents` (`api/v1/documents.py`:89) | Signed in |
| POST | `/api/v1/documents` | `upload_document` (`api/v1/documents.py`:95) | Signed in |
| POST | `/api/v1/documents/job-description` | `paste_job_description` (`api/v1/documents.py`:158) | Signed in |
| GET | `/api/v1/documents/{doc_id}` | `get_document` (`api/v1/documents.py`:182) | Signed in |
| GET | `/api/v1/documents/{doc_id}/download` | `download_document` (`api/v1/documents.py`:187) | Signed in |
| DELETE | `/api/v1/documents/{doc_id}` | `delete_doc` (`api/v1/documents.py`:206) | Signed in |
| POST | `/api/v1/documents/{doc_id}/confirm-skills` | `confirm_skills` (`api/v1/documents.py`:233) | Signed in |
| POST | `/api/v1/documents/compare` | `compare` (`api/v1/documents.py`:259) | Signed in |
| GET | `/api/v1/health/live` | `live` (`api/v1/health.py`:13) | Public |
| GET | `/api/v1/health/ready` | `ready` (`api/v1/health.py`:18) | Public |
| GET | `/api/v1/mentor/status` | `mentor_status` (`api/v1/mentor.py`:41) | Signed in |
| GET | `/api/v1/mentor/conversations` | `list_conversations` (`api/v1/mentor.py`:53) | Signed in |
| GET | `/api/v1/mentor/conversations/{conversation_id}` | `get_conversation` (`api/v1/mentor.py`:73) | Signed in |
| DELETE | `/api/v1/mentor/conversations/{conversation_id}` | `delete_conversation` (`api/v1/mentor.py`:99) | Signed in |
| POST | `/api/v1/mentor/ask` | `ask` (`api/v1/mentor.py`:159) | Signed in |
| GET | `/api/v1/knowledge-graph` | `knowledge_graph` (`api/v1/planning.py`:35) | Signed in |
| GET | `/api/v1/knowledge-graph/insights` | `graph_insights` (`api/v1/planning.py`:53) | Signed in |
| POST | `/api/v1/roadmaps/generate` | `generate` (`api/v1/planning.py`:86) | Signed in |
| GET | `/api/v1/roadmaps/active` | `get_active` (`api/v1/planning.py`:99) | Signed in |
| GET | `/api/v1/roadmaps` | `list_roadmaps` (`api/v1/planning.py`:107) | Signed in |
| GET | `/api/v1/roadmaps/{roadmap_id}` | `get_roadmap` (`api/v1/planning.py`:127) | Signed in |
| GET | `/api/v1/roadmaps/{roadmap_id}/compare/{other_id}` | `compare` (`api/v1/planning.py`:132) | Signed in |
| PATCH | `/api/v1/roadmaps/items/{item_id}` | `update_item` (`api/v1/planning.py`:151) | Signed in |
| PUT | `/api/v1/roadmaps/{roadmap_id}/order` | `reorder` (`api/v1/planning.py`:187) | Signed in |
| GET | `/api/v1/progress/timeline` | `progress_timeline` (`api/v1/planning.py`:216) | Signed in |
| GET | `/api/v1/privacy/consents` | `get_consents` (`api/v1/privacy.py`:26) | Signed in |
| PUT | `/api/v1/privacy/consents/{purpose}` | `put_consent` (`api/v1/privacy.py`:35) | Signed in |
| GET | `/api/v1/privacy/policy` | `policy` (`api/v1/privacy.py`:49) | Public |
| GET | `/api/v1/privacy/export` | `export` (`api/v1/privacy.py`:74) | Signed in |
| POST | `/api/v1/privacy/delete-account` | `delete_account` (`api/v1/privacy.py`:92) | Signed in |
| POST | `/api/v1/feedback` | `feedback` (`api/v1/privacy.py`:121) | Signed in |
| GET | `/api/v1/feedback` | `my_feedback` (`api/v1/privacy.py`:129) | Signed in |
| GET | `/api/v1/staff/students` | `list_students` (`api/v1/staff.py`:60) | Mentor or admin |
| GET | `/api/v1/staff/students/{student_id}/overview` | `student_overview` (`api/v1/staff.py`:87) | Mentor or admin |
| POST | `/api/v1/staff/students/{student_id}/assessments` | `record_assessment` (`api/v1/staff.py`:155) | Mentor or admin |
| POST | `/api/v1/staff/students/{student_id}/verify` | `verify_item` (`api/v1/staff.py`:196) | Mentor or admin |
| POST | `/api/v1/staff/students/{student_id}/readiness-labels` | `record_label` (`api/v1/staff.py`:236) | Mentor or admin |
| GET | `/api/v1/staff/verification-queue` | `verification_queue` (`api/v1/staff.py`:261) | Mentor or admin |
| GET | `/api/v1/staff/assessments` | `assessment_catalogue` (`api/v1/staff.py`:282) | Mentor or admin |
| GET | `/api/v1/profile` | `get_profile` (`api/v1/twin.py`:106) | Signed in |
| PUT | `/api/v1/profile` | `update_profile` (`api/v1/twin.py`:111) | Signed in |
| PATCH | `/api/v1/profile` | `patch_profile` (`api/v1/twin.py`:127) | Signed in |
| PUT | `/api/v1/profile/roles` | `update_role_preferences` (`api/v1/twin.py`:144) | Signed in |
| POST | `/api/v1/profile/onboarding/complete` | `complete_onboarding` (`api/v1/twin.py`:162) | Signed in |
| GET | `/api/v1/twin/skills` | `list_skills` (`api/v1/twin.py`:175) | Signed in |
| PUT | `/api/v1/twin/skills/{skill_id}` | `rate_skill` (`api/v1/twin.py`:214) | Signed in |
| PUT | `/api/v1/twin/skills` | `rate_skills_bulk` (`api/v1/twin.py`:227) | Signed in |
| DELETE | `/api/v1/twin/skills/{skill_id}` | `clear_skill_rating` (`api/v1/twin.py`:244) | Signed in |
| GET | `/api/v1/twin/projects` | `list_projects` (`api/v1/twin.py`:306) | Signed in |
| POST | `/api/v1/twin/projects` | `create_project` (`api/v1/twin.py`:313) | Signed in |
| PUT | `/api/v1/twin/projects/{project_id}` | `update_project` (`api/v1/twin.py`:326) | Signed in |
| DELETE | `/api/v1/twin/projects/{project_id}` | `delete_project` (`api/v1/twin.py`:341) | Signed in |
| GET | `/api/v1/twin/experiences` | `list_experiences` (`api/v1/twin.py`:351) | Signed in |
| POST | `/api/v1/twin/experiences` | `create_experience` (`api/v1/twin.py`:358) | Signed in |
| PUT | `/api/v1/twin/experiences/{experience_id}` | `update_experience` (`api/v1/twin.py`:370) | Signed in |
| DELETE | `/api/v1/twin/experiences/{experience_id}` | `delete_experience` (`api/v1/twin.py`:386) | Signed in |
| GET | `/api/v1/twin/certifications` | `list_certifications` (`api/v1/twin.py`:396) | Signed in |
| POST | `/api/v1/twin/certifications` | `create_certification` (`api/v1/twin.py`:405) | Signed in |
| DELETE | `/api/v1/twin/certifications/{certification_id}` | `delete_certification` (`api/v1/twin.py`:417) | Signed in |
| GET | `/api/v1/twin/assessments` | `list_assessment_results` (`api/v1/twin.py`:443) | Signed in |
| POST | `/api/v1/twin/assessments` | `add_self_reported_assessment` (`api/v1/twin.py`:466) | Signed in |
| DELETE | `/api/v1/twin/assessments/{result_id}` | `delete_self_reported_assessment` (`api/v1/twin.py`:489) | Signed in |
| POST | `/api/v1/twin/verification-requests` | `request_verification` (`api/v1/twin.py`:499) | Signed in |
| GET | `/api/v1/twin/snapshots` | `list_snapshots` (`api/v1/twin.py`:516) | Signed in |
| GET | `/api/v1/twin/diff` | `diff_snapshots` (`api/v1/twin.py`:537) | Signed in |
| GET | `/api/v1/twin/completeness` | `get_completeness` (`api/v1/twin.py`:559) | Signed in |

### Router-by-router summary

| Router | Purpose | Main tables read/written | Validation and security specifics | Tests |
|---|---|---|---|---|
| `auth.py` (261 lines) | §4 | users, user_sessions, auth_tokens, consents, student_profiles, audit_events | Identical responses for existing/non-existing accounts; e-mail in the background | `test_auth.py` (19) |
| `twin.py` (561) | Profile, role preferences, onboarding, skill ratings, projects/experiences/certifications with evidence, assessments, verification requests, snapshots, diff, completeness | student_profiles, student_role_preferences, student_skills, projects, experiences, certifications, skill_evidence, assessment_results, twin_snapshots | Every query filters `user_id == principal.id`; `_owned` (L295) returns the same 404 for "missing" and "not yours"; editing a verified item resets it to unverified; attendance stored only with the `attendance_data` consent | `test_twin.py` (12) |
| `career.py` | Roles/catalogue, readiness, gaps, sensitivity, simulations, scenarios, features | career_roles, role_skill_requirements, predictions, twin_snapshots, what_if_scenarios | Rate limits `EXPENSIVE_USER` (60/10 min) and `SIMULATION_USER` (120/10 min); max 50 saved scenarios | `test_career.py` (15) |
| `planning.py` (251) | Knowledge graph + insights, roadmaps, progress timeline | roadmaps, roadmap_items, roadmap_events, predictions, twin_snapshots | Ownership checks on roadmap and items; reorder warns when a prerequisite would come after its dependant | `test_planning.py` (8) |
| `mentor.py` (292) | Mentor status, conversations, streamed answers | mentor_conversations, mentor_messages | Question length limit (2000 characters); `MENTOR_USER` (20/10 min); 503 when Ollama or a model is missing | `test_rag.py` (12) |
| `documents.py` | Upload, analyse, download, delete, confirm skills, compare | documents, student_skills | Content sniffing, size limit, `UPLOAD_USER` (20/h), max documents per user, attachment download with nosniff | `test_documents_privacy.py` (9) |
| `privacy.py` (145) | Consents, policy, export, deletion, feedback | consents, all owned tables, user_feedback | Deletion requires the password and the exact phrase `DELETE MY ACCOUNT`; `FEEDBACK_USER` (30/h) | `test_documents_privacy.py`, `test_staff_admin.py` |
| `staff.py` | Mentor tools | users, mentor_links, consents, assessment_results, projects, experiences, certifications, readiness_labels | Link + consent gate; RLS subject switched to the student; labels frozen to a snapshot and tagged with research consent | `test_staff_admin.py` (9) |
| `admin.py` | System, retention, audit, feedback, users, mentor links, roles, skills, prerequisites, resources, models, knowledge base | all catalogue tables, users, model_versions, documents, audit_events, user_feedback | Admin role; `privileged_scope` for catalogue writes; prerequisite cycles rejected; SSRF-guarded link validation; model activation re-verifies the artifact first | `test_staff_admin.py` |
| `health.py` (35) | Liveness / readiness | — / `SELECT 1` | `/live` touches nothing (safe for uptime pingers); `/ready` reports database, model, mentor LLM | indirectly |

## Endpoints without a user interface

My automatic scan flagged fifteen operations as never called by the React app. Checking each path by text search showed
that **seven operations are genuinely API-only** (the two probes share a row below):

| Operation | Purpose | Comment |
|---|---|---|
| `POST /api/v1/admin/roles` | Create a new role | No "create role" screen; the admin Roles tab edits existing roles |
| `POST /api/v1/admin/skills` | Create a skill | No screen |
| `PUT /api/v1/admin/skills/{skill_id}/prerequisites` | Set prerequisites (cycle-checked) | No screen |
| `GET /api/v1/roles/{role_id}` | One role with requirements | UI uses the list endpoint |
| `GET /api/v1/roadmaps/{roadmap_id}` | One roadmap | UI uses `active`, list and compare |
| `GET /api/v1/health/live`, `/health/ready` | Probes | For Docker, Render and uptime monitors, by design |

The other eight (`GET /admin/system`, `POST /admin/retention/run`, `GET /admin/audit`, `GET /admin/models`,
`GET /admin/knowledge`, `GET /auth/csrf`, `GET /mentor/status`, `GET /privacy/policy`) *are* used by the UI. The
scan missed them because of nested TypeScript generics in the call (for example `api<Record<string, number>>(…)`).

## 6. Services (summary; deep dives elsewhere)

| Service | Responsibility | Deep dive |
|---|---|---|
| `services/twin/state.py` | `TwinState` snapshot, deep `clone`, content hash, loader | [08](08-digital-twin-roles-and-simulator.md) |
| `services/twin/proficiency.py` | Evidence-trust estimation | [08](08-digital-twin-roles-and-simulator.md) |
| `services/twin/features.py` | 19-feature vector | [05](05-machine-learning-deep-dive.md) |
| `services/twin/history.py` | Snapshots, completeness, diffs | [08](08-digital-twin-roles-and-simulator.md) |
| `services/catalogue.py` | Cached reference catalogue keyed by a DB fingerprint (counts and max timestamps of 10 catalogue tables, L98–111) | below |
| `services/career/gap_engine.py` | Match and gap formula, sensitivity | [08](08-digital-twin-roles-and-simulator.md) |
| `services/career/readiness.py` | Inference, warnings, explanation | [05](05-machine-learning-deep-dive.md) |
| `services/career/simulator.py` | What-if | [08](08-digital-twin-roles-and-simulator.md) |
| `services/career/knowledge_graph.py`, `roadmap.py` | Graph and roadmap | [09](09-knowledge-graph-and-roadmap.md) |
| `services/rag/*` | Mentor and RAG | [06](06-llm-and-ollama-deep-dive.md), [07](07-rag-pipeline-deep-dive.md) |
| `services/documents/*` | Upload safety, parsing | [14](14-resume-and-job-description-processing.md) |
| `services/privacy.py` | Export L98–142, deletion L152–165, retention L168–200 | [11](11-security-review.md) |
| `services/link_checker.py` | SSRF-guarded HTTPS checks | [11](11-security-review.md) |

**Catalogue caching** (`services/catalogue.py` L114–): the catalogue (skills, roles, requirements, prerequisites,
resources, assessments) is loaded into frozen dataclasses and cached per process. It is reloaded when the
fingerprint changes. The cache holds only global reference data, never student data, so it can't leak information
between users.

## 7. Models, schemas and seed data

* **ORM models** (`backend/app/models/*.py`, 978 lines) map 35 tables. Primary keys are PostgreSQL 18 `uuidv7()`
  (time-ordered, not guessable) except catalogue tables, which use integers. See
  [10-database-and-data-model.md](10-database-and-data-model.md).
* **Schemas** (`backend/app/schemas/*.py`): request models are strict; response models use `from_attributes=True`.
* **Seed** (`backend/app/seed/catalogue.py` `seed_catalogue` L41) is idempotent: it inserts only what's missing and
  never overwrites admin edits. Data (`seed/catalogue_data.py`, 1,397 lines) is 42 skills with aliases, 33
  prerequisite edges, 6 roles (AI/ML Engineer, Backend Developer, Data Analyst, Data Scientist, Full-Stack Developer,
  Software Developer) with 91 requirements, 7 assessments and 50 learning resources. `_validate_static_data` (L24)
  checks references and cycles before inserting.

## 8. Command-line interface

`python -m app.cli <command>` (`backend/app/cli.py`, `main` L145):

| Command | Function (line) | What it does |
|---|---|---|
| `seed` | `cmd_seed` L24 | Idempotent catalogue load |
| `deploy-init` | `cmd_deploy_init` L32 | Seed + register shipped model artifacts; activate one if no model is active (`app/ml/artifacts.py` `register_bundled`) |
| `serve-hosted` | `cmd_serve_hosted` L44 | Alembic upgrade + deploy-init + uvicorn in one process (Render) |
| `validate-links` | `cmd_validate_links` L71 | Checks every learning-resource URL (SSRF-guarded), updates `verification_status` |
| `reindex-kb` | `cmd_reindex_kb` L85 | Re-embeds `knowledge/*.md` + generated role guides (needs Ollama) |
| `create-admin EMAIL` | `cmd_create_admin` L93 | Prompts for a password (policy-checked) and creates or promotes an admin |
| `retention` | `cmd_retention` L120 | Applies the retention policy |
| `models` | `cmd_models` L128 | Lists registered model versions |
| `bench-mentor` | `cmd_bench_mentor` L139 | Local LLM latency/throughput/VRAM benchmark |

## 9. Error cases worth knowing

| Situation | Response | Where |
|---|---|---|
| Missing `X-Requested-With` or a foreign `Origin` on an unsafe API call | 403 `csrf_header_missing` / `origin_rejected` | `middleware.py` L74–83 |
| Wrong or missing CSRF token | 403 `csrf_invalid` (the frontend refreshes once and retries) | `deps.py` L73–76, `frontend/src/lib/api.ts` L119–122 |
| Not signed in or session expired | 401 `unauthenticated` | `deps.py` L81–82 |
| Too many requests | 429 `rate_limited` + `Retry-After` | `errors.py` L55–62, `ratelimit.py` |
| Body too large | 413 `payload_too_large` | `middleware.py` L85–103 |
| Unknown field, wrong type, out of range | 422 `validation_error` with field list | `errors.py` L84–94 |
| Resource not found **or not owned** | 404 (identical message) | e.g. `twin.py` `_owned` L295 |
| Unique or foreign-key violation | 409 `conflict` (constraint name logged only) | `errors.py` L102–107 |
| Database unreachable | 503 `database_unavailable` | `errors.py` L109–112 |
| Readiness model missing or invalid | 200 with `available: false` and a reason (no score is fabricated) | `career.py` L148–155 |
| Ollama or model missing | 503 `mentor_unavailable`; during streaming an SSE `error` event | `mentor.py` L170–172, L268–282 |
| Unexpected exception | 500 `internal_error`, details only in the server log | `errors.py` L114–117 |

## 10. Notable implementation details and minor issues

| Item | Location | Note |
|---|---|---|
| Lock-ordering fix in login | `auth_service.py` L182–189 | `FOR NO KEY UPDATE` plus a rollback before the standalone audit avoids a deadlock with the audit FK |
| `_me` scopes RLS before reading the profile | `auth.py` L75–86 | Without it, `onboarding_completed` was wrong right after login (regression test `test_login_response_reflects_completed_onboarding`) |
| Upload written before commit | `documents.py` L112–116 | If the DB insert later fails, the file stays on disk (orphan); retention won't find it because no row exists |
| Mentor "busy" path | `mentor.py` L260–267 | The user's question is stored, but no assistant row is written |
| Unhandled errors inside the SSE stream | `mentor.py` L199–285 | Only `MentorBusy`, `OllamaUnavailable` and `TimeoutError` are handled; anything else ends the stream without an `error` event |
| Unused helper | `services/rag/mentor.py` L370 `catalogue_hint` | Never called |
| Leftover `if True:` | `services/rag/mentor.py` L155 | Harmless |
| Comments pointing to missing docs | `gap_engine.py` L3, `proficiency.py` L4, `roadmap.py` L1, `career.py`, `ratelimit.py`, `Dockerfile` | `docs/methodology/{skill-gap,proficiency,roadmap}.md` and `docs/deployment.md` don't exist; the content lives in `docs/methodology/README.md` and `docs/operations/deployment.md` |
| Nonexistent CLI command in a comment | `security/passwords.py` L10 | `bench-argon2` isn't implemented |
| Verification queue ignores assessments | `staff.py` L261–278 | Uses `EVIDENCE_MODELS` (projects, experiences, certifications) only |
