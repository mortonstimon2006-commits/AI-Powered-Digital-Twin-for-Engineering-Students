# Dependency vulnerability exceptions

Every exception must state why the vulnerability is not reachable, how that was verified, and when it expires.
Exceptions are scoped by advisory ID in CI (`--ignore-vuln`), never by package.

## chromadb 1.5.9 — Chroma HTTP-server advisories (recorded 2026-10-14)

| Advisory | Summary | Fixed version |
|---|---|---|
| PYSEC-2026-311 / CVE-2026-45829 | Pre-auth code injection via `trust_remote_code` on the server's collection-creation endpoint | none yet |
| PYSEC-2026-3814 / CVE-2026-45833 | Authenticated code injection via the server's collection-update endpoint | none yet |
| PYSEC-2026-3815 / CVE-2026-45831 | `SimpleRBACAuthorizationProvider` ignores tenant/database scope | none yet |
| PYSEC-2026-3813 / CVE-2026-45830 | Missing tenant authorisation in the server API | none yet |

**Why it is not reachable in TwinPath:** all four issues are in Chroma's **HTTP server** and its auth providers.
TwinPath uses only the embedded `chromadb.PersistentClient` inside the API process. No Chroma server is started,
no Chroma port exists in any compose file, and collections are created only by TwinPath code with a fixed
configuration and `embedding_function=None` (embeddings come from Ollama). Users cannot influence collection
configuration or model loading.

**Verified by:** code search finds no `HttpClient`/server usage in `backend/app`. The compose files define no
Chroma service.

**Expiry and conditions:**
* Re-check on every chromadb release and upgrade as soon as a fixed version exists.
* The exception is **void** if Chroma is ever deployed as a separate server; the fixes become mandatory first.
