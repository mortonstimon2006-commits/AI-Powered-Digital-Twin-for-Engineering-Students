# Threat model

Scope: the AI Career Guidance App web SPA, FastAPI API, PostgreSQL, the embedded Chroma store, the local Ollama runtime and
uploaded files. Method: STRIDE-style review per asset and trust boundary.

Operator go-live steps: [security checklist](checklist.md).

**Not performed:** no penetration test has been carried out. Controls below are verified by the automated tests
cited, plus code review.

## Assets

Student profiles and evidence, assessor labels, uploaded resumes, mentor conversations, session credentials, the
model artifact (pickle), the role catalogue and the audit trail.

## Trust boundaries

1. Browser ↔ edge proxy/nginx (public, TLS in staging and production).
2. nginx ↔ API (private network).
3. API ↔ PostgreSQL (private network, least-privilege role, TLS when not co-located).
4. API ↔ Ollama (loopback or private network only, never public).
5. API ↔ untrusted file content and model output.

## Threats and controls

| # | Threat | Controls | Evidence |
|---|---|---|---|
| T1 | Broken access control / IDOR | Every query filters on the session user's id, never one from the client. "Not found" responses are identical for "doesn't exist" and "belongs to someone else". **PostgreSQL row-level security** on 20 student-owned tables (app role has no BYPASSRLS). Mentors need an admin link **and** live student consent. | `test_cross_user_isolation_idor`, `test_rls_blocks_cross_user_rows_under_app_role`, `test_roadmap_isolation`, `test_saved_scenarios_are_private`, `test_document_access_control_and_deletion`, `test_conversations_are_private`, `test_mentor_access_requires_link_and_consent` |
| T2 | SQL injection | SQLAlchemy parameterised queries only. No string-built SQL from user input. The mentor has no SQL or tool access. | code review, ruff `S` rules |
| T3 | XSS | React escaping. ESLint bans `dangerouslySetInnerHTML`. Model output goes through a text-only markdown subset, with links rendered only for https catalogue URLs. Strict CSP (`script-src 'self'`). | `SafeMarkdown` tests |
| T4 | CSRF (incl. login CSRF) | SameSite=Lax HttpOnly session cookie. Per-session synchroniser token checked on every unsafe request. A custom `X-Requested-With` header is required on all unsafe `/api` requests (cross-site forms can't send it, and cross-origin fetch triggers a rejected preflight). Origin allow-list. | `test_csrf_and_origin_protections` |
| T5 | Credential stuffing / brute force | Argon2id. Per-IP and per-account sliding-window limits. Exponential lockout. Common-password blocklist and minimum 12 characters. Optional TOTP MFA. | `test_lockout_after_repeated_failures`, `test_login_rate_limit`, `test_mfa_enrolment_login_and_disable` |
| T6 | Account enumeration | Identical responses for register, login and password reset; equalised hashing work; emails sent after the response. | `test_register_is_non_enumerating…`, `test_login_errors_do_not_reveal…`, reset flow test |
| T7 | Session theft / fixation | 256-bit opaque tokens stored only as SHA-256. `__Host-` prefix in production. Idle and absolute expiry. Revocation on logout, password change or reset, and role change. Session list with revoke. | `test_logout_revokes_session`, `test_change_password_revokes_other_sessions`, `test_admin_user_management_revokes_sessions` |
| T8 | Malicious uploads | Type decided by content (magic bytes / container). PDF, DOCX and UTF-8 text only. Macro, encrypted and zip-bomb rejection. Size limit enforced in middleware and endpoint. Parsing in a separate process with timeout and page/char caps. Files outside web roots under random names. Download only as an attachment with nosniff. | `test_malicious_and_invalid_files_rejected` |
| T9 | Path traversal | Filenames sanitised to a basename. Stored paths are generated. Resolved paths must stay under the upload or artifact root. | `test_document_access_control_and_deletion`, registry traversal test |
| T10 | SSRF | Only the admin link checker fetches URLs: https only, every redirect hop re-resolved, private/loopback/link-local/metadata IPs rejected. Repo/demo/credential URLs are never fetched server-side. | `test_resource_ssrf_guard` |
| T11 | Prompt injection (documents / retrieval) | Retrieved text wrapped as untrusted data. Injection-pattern passages excluded from context and counted. Control tokens stripped. The model has **no tools**: student facts come from the backend, so it cannot reach other users or alter predictions. | `test_private_retrieval_is_owner_scoped_and_injection_filtered`, RAG eval G06 |
| T12 | Unauthorised RAG retrieval | Owner filter applied **inside** the vector query (before similarity search), from the session user id. Global KB is reference data only. | same tests + eval G07 |
| T13 | Model hallucination presented as fact | Authoritative student context from the DB. Readiness numbers quoted, never computed by the LLM. Numbers absent from context flagged to the user. **Links not in the verified catalogue removed server-side.** Retrieved evidence shown separately from generated advice. | `test_unverified_numbers_flagged`, `test_sanitize_links_removes_uncatalogued_urls`, RAG eval G02/G03/G09 |
| T14 | Malicious/tampered model artifact (pickle) | Artifacts loaded only from the artifact directory after SHA-256 verification against the DB record, schema-hash and library-version checks; activation re-verifies. | `test_registry_rejects_tampered_or_mismatched_artifacts`, `test_model_activation_refuses_tampered_artifact` |
| T15 | Sensitive-data exposure in logs/errors | JSON logs with key-based redaction and email masking. Uvicorn access log disabled (no query strings). Generic 500s with a request id. No stack traces. `debug=False` always. | `test_security_headers_and_error_envelope` |
| T16 | Cross-user cache contamination | `Cache-Control: no-store` on all API responses. Server caches hold only global reference data (catalogue, global graph). Student overlays computed per request. | code review |
| T17 | DoS / resource exhaustion | Body-size limit, request rate limits (auth, mentor, uploads, simulations, expensive endpoints), DB statement and lock timeouts for the app role, bounded mentor concurrency with a bounded queue, parse timeouts, output token caps. | `test_oversized_body_rejected`, mentor limit tests |
| T18 | Insecure CORS | Explicit origin allow-list with credentials; the dev setup uses a same-origin proxy. | config validation |
| T19 | Debug/insecure config in production | Settings fail closed in staging/production: https origins, Secure cookies, no file email backend, no placeholder DB passwords. API docs disabled by default. | `config.py` validator |
| T20 | Secrets leakage | `.env` git-ignored, sanitised `.env.example`, CI secrets generated per run, gitleaks in CI (clean on 2026-10-14). | CI `secrets` job |
| T21 | Dependency/container vulnerabilities | Locked dependencies (uv.lock, package-lock.json), pip-audit, npm audit, Trivy image scan in CI, digest-pinned base images, non-root read-only containers with all capabilities dropped. | CI; see [dependency exceptions](dependency-exceptions.md) |
| T22 | Excessive retention | Configurable retention for documents and chats, purge job (CLI and admin), hard account deletion including files and vectors, data export. | `test_retention_removes_expired_documents`, `test_account_deletion_is_complete` |
| T23 | Audit tampering | Audit table is append-only for the app role (no UPDATE/DELETE/TRUNCATE). | RLS test asserts `DELETE` is denied |
| T24 | Ollama exposure | Bound to loopback by default. Never published by compose. Documented private-network topology only. | [deployment guide](../operations/deployment.md) |

## Residual risks

Single-process rate limiting (multi-replica deployments need a shared store). No breached-password corpus.
TOTP codes are not replay-tracked within their 30-second window (the challenge itself is single-use). Heuristic
prompt-injection detection can be evaded; the structural mitigations (no tools, owner-scoped retrieval) are the
real defence. No independent penetration test has been done.
