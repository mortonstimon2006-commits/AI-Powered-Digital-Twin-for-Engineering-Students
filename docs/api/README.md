# API reference

* Machine-readable specification: [`openapi.json`](openapi.json) (OpenAPI 3.1, generated from the code: 106 paths,
  124 operations).
* Interactive docs in development: `http://localhost:5173/api/docs` (Swagger) and `/api/redoc`. They are
  **disabled by default in staging and production** (`ENABLE_API_DOCS`).
* Base path: `/api/v1`. Every route is versioned.

## Conventions

| Topic | Convention |
|---|---|
| Authentication | Opaque session cookie (`__Host-tp_session` in production, HttpOnly, Secure, SameSite=Lax). Obtained from `POST /auth/login`. |
| CSRF | Every POST/PUT/PATCH/DELETE must send `X-Requested-With: twinpath`. Authenticated ones must also send `X-CSRF-Token` with the value of the `__Host-tp_csrf` cookie. `GET /auth/csrf` re-issues the token. |
| Errors | `{"error": {"code": "...", "message": "...", "details": [...], "request_id": "..."}}`. Validation errors use code `validation_error` and list `details[].field`. No stack traces, SQL or paths. |
| Validation | Request bodies reject unknown fields (`extra=forbid`) and enforce ranges. Query parameters are bounded. |
| Pagination | `limit` (bounded, usually ≤ 200) and `offset`. Responses include `limit`/`offset` and, for admin lists, `total`. |
| Limits | Request bodies ≤ upload limit + 64 KB. Rate limits return `429` with `Retry-After`. |
| Caching | All API responses are `Cache-Control: no-store`. |
| Streaming | `POST /mentor/ask` returns Server-Sent Events: `meta` (sources, context sections) → `status` → `delta`* → `done` (final sanitised `content`, `unverified_numbers`, `removed_links`, token counts) or `error`. |

## Route groups

| Group (tag) | Prefix | Operations | Notes |
|---|---|---:|---|
| health | `/health` | 2 | `live`, `ready` |
| auth | `/auth` | 17 | register, login (+MFA), logout, me, csrf, sessions, password change/forgot/reset, email verify/resend, MFA setup/verify/disable |
| digital-twin | `/profile`, `/twin` | 27 | profile (PUT/PATCH), role preferences, onboarding, skills, projects, experiences, certifications, assessments, verification requests, snapshots, diff, completeness, features |
| career-intelligence | `/roles`, `/catalogue`, `/readiness`, `/skill-gaps`, `/simulations` | 15 | role catalogue is public reference data; everything else requires a session |
| planning | `/knowledge-graph`, `/roadmaps`, `/progress` | 10 | |
| mentor | `/mentor` | 5 | local Ollama only; returns `503 mentor_unavailable` rather than any fallback |
| documents | `/documents` | 8 | upload, JD paste, download (attachment), delete, confirm skills, compare |
| privacy | `/privacy`, `/feedback` | 7 | consents, policy, export, account deletion, feedback |
| mentor-tools | `/staff` | 7 | mentor/admin only; requires assignment **and** student consent |
| admin | `/admin` | 26 | admin only; every mutation is audited; feedback list is returned without user identity |
