# Incident response and credential rotation

## Severity triage

| Severity | Examples | First response |
|---|---|---|
| Critical | Evidence of cross-student data access, leaked DB credentials, compromised admin account | Contain within 1 hour; notify the institution's data-protection contact |
| High | Exploitable vulnerability with no evidence of use; leaked SECRET_KEY | Patch or mitigate within 24 hours |
| Medium/Low | Hardening gaps, dependency advisories that are not reachable | Next planned release |

## Containment playbook

1. **Preserve evidence:** export `audit_events` for the period (`GET /api/v1/admin/audit` or SQL as owner) and keep
   the API logs. Audit rows cannot be modified by the app role.
2. **Cut access:** deactivate affected accounts (Admin → Users). This revokes their sessions immediately. To
   revoke **all** sessions: `UPDATE user_sessions SET revoked_at = now() WHERE revoked_at IS NULL;` (owner role).
3. **Stop the mentor if relevant:** stop Ollama or set `OLLAMA_BASE_URL` to an unreachable address. The rest of
   the app degrades gracefully.
4. **Patch, test** (`pytest`, `npm test`, CI) and redeploy using the [deployment guide](../operations/deployment.md).
5. **Notify** affected students and the institution as required by applicable law.

## Credential rotation

| Secret | How to rotate | Side effects |
|---|---|---|
| `TWINPATH_APP_PASSWORD` / `TWINPATH_OWNER_PASSWORD` | `ALTER ROLE twinpath_app PASSWORD '…'` (as superuser), update the secret store and `.env`, restart the API | brief reconnect |
| `SECRET_KEY` | generate (`python -c "import secrets;print(secrets.token_urlsafe(48))"`), deploy | rate-limit buckets reset; pseudonymous audit references change |
| `FIELD_ENCRYPTION_KEY` | **cannot simply be replaced:** MFA secrets are encrypted with it. Plan: deploy a key-rotation release that decrypts with the old key and re-encrypts with the new one, or require affected users to re-enrol MFA | MFA re-enrolment if keys are swapped without re-encryption |
| Session tokens | revoke all sessions (above) | everyone signs in again |
| SMTP credentials | rotate with the mail provider, update the secret | none |

Never paste secrets into tickets, chat or logs. Store production secrets in the platform's secret manager, not in
files on shared drives.
