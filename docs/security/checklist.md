# Security checklist

There are two parts:

* **A — built into the code:** controls already in the code and checked by CI. A regression here is a bug.
* **B — go-live:** what an operator must do and confirm for each deployment. Nothing in B can be verified from
  inside this repository.

Threat-by-threat rationale is in the [threat model](threat-model.md).

## A. Built-in controls (verified 2026-10-14)

| Area | Control | Verified by |
|---|---|---|
| Passwords | Argon2id; minimum 12 characters; common-password blocklist; rehash on parameter change | `test_auth.py` |
| Sessions | Opaque 256-bit tokens, stored only as SHA-256; HttpOnly, SameSite=Lax, Secure/`__Host-` when `COOKIE_SECURE=true`; idle and absolute expiry; revoked on logout, password change/reset and role change | `test_auth.py`, `test_staff_admin.py` |
| CSRF | Synchroniser token, the required `X-Requested-With: twinpath` header on unsafe `/api` calls, and an Origin allow-list | `test_csrf_and_origin_protections` |
| Brute force | Per-IP and per-account limits; exponential lockout; optional TOTP MFA with an encrypted secret | `test_lockout_*`, `test_login_rate_limit`, `test_mfa_*` |
| Enumeration | Identical register/login/reset responses | `test_register_is_non_enumerating…` |
| Access control | Ownership filter in every query; PostgreSQL RLS on 20 student tables; app role is `NOBYPASSRLS`; mentor access = admin link **and** live consent | IDOR and RLS tests |
| Audit | Append-only for the app role | RLS test (DELETE denied) |
| Uploads | Content sniffing; PDF/DOCX/TXT only; macro, encrypted and zip-bomb rejection; size limit; parsing in a subprocess with a timeout; random names outside the web root; attachment download with nosniff | `test_malicious_and_invalid_files_rejected` |
| SSRF | Link checker: https only; each redirect re-resolved; private, loopback, link-local and metadata addresses blocked | `test_resource_ssrf_guard` |
| Model artifacts | SHA-256, schema-hash and library-version verification before loading and at activation | registry tests |
| LLM | Local Ollama only; no tools; owner-scoped retrieval; injection-flagged passages excluded; non-catalogue links removed; unverified numbers flagged | `test_rag.py`, RAG eval |
| Output | Strict CSP (`script-src 'self'`); no `dangerouslySetInnerHTML` (lint rule); https-only links in rendered markdown | nginx config, ESLint, `SafeMarkdown` tests |
| Headers | API: `no-store`, nosniff, `default-src 'none'; frame-ancestors 'none'` CSP. SPA (nginx): strict CSP, X-Frame-Options DENY, `Referrer-Policy: no-referrer`, Permissions-Policy | `test_security_headers_and_error_envelope` (API); `frontend/nginx.conf` (SPA, checked in the container run) |
| Errors and logs | Generic 500s with a request id; JSON logs with redaction; `debug=False` always | same test |
| Config | Fails closed when `TWINPATH_ENV` is staging/production: Secure cookies, https origins, no file email backend, SMTP if verification is required, no placeholder DB password, `SECRET_KEY` ≥ 32 chars | `config.py` validator |
| Supply chain | `uv.lock`, `package-lock.json`, digest-pinned images; pip-audit, npm audit, gitleaks and Trivy in CI | `.github/workflows/ci.yml` |
| Containers | Non-root, read-only root filesystem, `cap_drop: ALL`, `no-new-privileges`; DB and Ollama not published | `docker-compose.yml` |

## B. Go-live checklist (operator; not verifiable from this repository)

Tick every item for each environment and keep the signed copy with the release record.

### Secrets and configuration
- [ ] `TWINPATH_ENV=production` (or `staging`) and the API starts. The validator refuses unsafe settings.
- [ ] `SECRET_KEY` and `FIELD_ENCRYPTION_KEY` are generated freshly for this environment. They are never reused
      from development and are stored in the platform's secret manager, not in a file in the image.
- [ ] Database passwords for `twinpath_owner` and `twinpath_app` are unique. The API uses **only** the app role;
      the owner role is used only by the migration job.
- [ ] `ALLOWED_ORIGINS` lists only the real https origin(s).
- [ ] `TRUST_PROXY_HEADERS=true` **only** when the API is reachable solely through your own proxy, which overwrites
      `X-Forwarded-For`. Otherwise clients could spoof their IP and dodge per-IP rate limits.
- [ ] `ENABLE_API_DOCS` is unset or false.
- [ ] SMTP is configured and a real verification and reset email has been received end to end.

### Network
- [ ] TLS is terminated at the edge (see `infra/caddy/Caddyfile`). HTTP redirects to HTTPS, HSTS is enabled
      after HTTPS has been confirmed, and a certificate-expiry alert is in place.
- [ ] Only the edge is reachable from the internet. PostgreSQL, the API container port and Ollama are not.
      Confirm with an external port scan of the public address.
- [ ] Ollama listens on loopback or a private interface, with a firewall rule limiting it to the API host.
- [ ] PostgreSQL uses TLS when it is not on the same host as the API.

### Data protection
- [ ] Encryption at rest is **actually enabled** for the database volume or managed instance, the uploads volume,
      the Chroma directory and the backups. Record how it was confirmed. Running PostgreSQL does not provide it by itself.
- [ ] Retention periods (`DOCUMENT_RETENTION_DAYS`, chat retention) are set to the agreed policy, and the purge job
      is scheduled.
- [ ] Privacy notice and consent text are approved by the institution. A data protection impact assessment
      exists if research use is enabled.

### Operations
- [ ] Automated backups are scheduled, and `infra/scripts/restore-check.sh` has passed **in this environment**.
- [ ] Logs ship to central storage with access control. A sample has been checked for absence of tokens,
      passwords and document text.
- [ ] Alerts exist for `/api/v1/health/ready` failures, 5xx rate, auth lockout spikes, disk usage and GPU/Ollama
      availability.
- [ ] The incident-response contacts in [incident-response.md](incident-response.md) are filled in.
- [ ] Rollback has been rehearsed (previous image tag plus `alembic downgrade` plan) in staging.
- [ ] Only one API process runs per deployment, **or** the in-process rate limiter has been replaced with a
      shared store.

### Models and content
- [ ] The active readiness model's card has been reviewed. If it is still the synthetic demonstration model,
      everyone involved understands it must not inform real decisions.
- [ ] `python -m app.cli validate-links` has run against the production catalogue, and broken resources are
      fixed or retired.
- [ ] The knowledge base has been re-indexed (`reindex-kb`) and spot-checked.
- [ ] The Ollama model tags and digests match the documented ones (`ollama list`).

### Assurance
- [ ] CI is green on the exact commit being deployed (tests, audits, gitleaks, Trivy).
- [ ] Dependency exceptions in [dependency-exceptions.md](dependency-exceptions.md) have been re-checked for
      fixes.
- [ ] Before any public or large-scale launch: an independent security review or penetration test has been
      completed and its findings resolved. **Not done as of 2026-10-14.**
