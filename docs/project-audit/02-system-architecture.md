# 02 — System architecture

## 1. The big picture

The system is a **single-page web application** (React) talking to a **REST + streaming API** (FastAPI). The API owns
all business logic and talks to five back-end stores and services:

| Component | Technology | Role | Where it runs |
|---|---|---|---|
| Web client | React 19, TypeScript strict, Vite 8, Tailwind 4, TanStack Query, Radix, React Three Fiber, Recharts, Motion | UI, routing, data fetching/caching, 3D and 2D visualisations | Browser |
| Web server (container mode) | nginx (unprivileged) | Serves the built SPA with a strict CSP; reverse-proxies `/api` to the API; passes SSE through unbuffered | `web` container, `127.0.0.1:8080` |
| API | FastAPI on uvicorn, one worker | Auth, twin, career engine, ML inference, RAG mentor, documents, privacy, staff/admin | Native `127.0.0.1:8010` (dev) or `api` container port 8000 (internal only) |
| Relational database | PostgreSQL 18 | All structured data; row-level security | `db` container, loopback port 5433 |
| Vector store | Chroma `PersistentClient` (embedded in the API process) | Embedded knowledge-base and private-document chunks | Files under `DATA_DIR/chroma` |
| File store | Local disk | Uploaded documents (outside any web root) | `DATA_DIR/uploads` |
| Model artifacts | joblib + JSON manifest | Readiness model bundle, checksum-verified | `MODEL_ARTIFACT_DIR` |
| Local LLM runtime | Ollama with `qwen3:8b` (chat) and `nomic-embed-text` (embeddings) | Mentor generation and embeddings | Host machine, `127.0.0.1:11434` |

## 2. Architecture diagram

```mermaid
flowchart LR
  subgraph Browser
    SPA["React SPA<br/>router.tsx · lib/api.ts · lib/sse.ts<br/>TanStack Query cache"]
  end

  subgraph Front["Entry (one of)"]
    Vite["Dev: Vite dev server :5173<br/>proxy /api → 127.0.0.1:8010"]
    Nginx["Containers: nginx :8080<br/>CSP · SPA fallback · /api proxy"]
    Vercel["Hosted (NOT VERIFIED): Vercel<br/>rewrite /api/* → Render"]
  end

  subgraph API["FastAPI process (app.main:create_app)"]
    MW["SecurityMiddleware + CORS<br/>(origin/header guard, size limit, headers)"]
    Routers["api/v1 routers<br/>auth · twin · career · planning · mentor ·<br/>documents · privacy · staff · admin · health"]
    Services["services/<br/>auth · twin · career · rag · documents · privacy"]
    ML["ml/registry + explain<br/>(active model in memory)"]
    Chroma[("Chroma PersistentClient<br/>kb_global · kb_private")]
  end

  PG[("PostgreSQL 18<br/>36 tables · RLS on 20")]
  Files[("Uploads folder")]
  Art[("Model artifact<br/>model.joblib + manifest.json")]
  Ollama["Ollama on host :11434<br/>qwen3:8b · nomic-embed-text"]

  SPA --> Vite --> MW
  SPA --> Nginx --> MW
  SPA -.-> Vercel -.-> MW
  MW --> Routers --> Services
  Services --> PG
  Services --> Chroma
  Services --> Files
  Services --> ML --> Art
  Services -- "HTTP /api/embed, /api/chat (stream)" --> Ollama
  Chroma -. "embeddings computed by" .-> Ollama
```

Dashed arrows mark the hosted path (Vercel → Render), which was verified only in a local simulation; on that host
the Ollama arrow does not exist, so the mentor reports itself unavailable
([12-docker-environment-and-deployment.md](12-docker-environment-and-deployment.md)).

## 3. Backend layering

```
HTTP request
  └─ SecurityMiddleware (backend/app/middleware.py)       request id · Origin + X-Requested-With guard · body limit · headers
     └─ CORSMiddleware (main.py L51–58)                   explicit origin allow-list, credentials
        └─ Router endpoint (backend/app/api/v1/*.py)      Pydantic validation (extra="forbid") · rate limits
           └─ Dependencies (backend/app/deps.py)          session cookie → Principal · CSRF check · RLS subject · role guard
              └─ Services (backend/app/services/**)       business logic; pure functions where possible
                 └─ db.py session                         every transaction sets app.user_id / app.privileged for RLS
                    └─ PostgreSQL (migrations 0001, 0002)
```

**Key design decision:** `TwinState` (`backend/app/services/twin/state.py` L86–124) is a plain-data snapshot of a
student. Proficiency estimation, features, gap analysis, readiness and the simulator are all functions of that
snapshot. That's why the simulator can reuse *exactly* the production pipeline on a deep copy
(`TwinState.clone()`, L99–100) without touching the database.

## 4. Who calls whom

| Caller | Callee | Sends | Receives | Stored where |
|---|---|---|---|---|
| Browser → API | JSON over HTTPS (or HTTP locally) with the session cookie; unsafe methods add `X-Requested-With: twinpath` and `X-CSRF-Token` | Request body (validated) | JSON envelope or SSE stream | Cookies in the browser; query cache in memory |
| API → PostgreSQL | psycopg 3 via SQLAlchemy 2 | SQL with bound parameters; `set_config` for RLS at each `BEGIN` | Rows | PostgreSQL volume |
| API → Chroma | In-process library calls | Embeddings + chunk text + metadata; queries with a `where` filter | Nearest chunks with cosine distances | `DATA_DIR/chroma` |
| API → Ollama `/api/embed` | `{"model": "nomic-embed-text", "input": [...], "truncate": true}` | Embedding vectors | Not stored by Ollama; stored in Chroma |
| API → Ollama `/api/chat` | System prompt + history + user block; `stream: true`, `think: false`, `num_ctx`, `temperature 0.3`, `num_predict 650` | Streamed JSON lines with text deltas and final token counts | Answer stored in `mentor_messages` |
| API → model registry | Feature vector (19 values; `None` = unknown) | Probabilities, SHAP values | Prediction stored in `predictions` |
| API → filesystem | Uploaded bytes under a random name | — | `DATA_DIR/uploads/<user_id>/…` |
| API → SMTP (optional) | Verification/reset e-mails | — | Not stored (development: `.eml` files in `DATA_DIR/outbox`) |

## 5. Sequence diagrams

All diagrams follow the code paths cited. Participants named *Svc* are Python modules, not separate services.

### 5.1 Student registration and authentication

Code: `backend/app/api/v1/auth.py` `register` L89–105, `login` L108–122; `backend/app/services/auth_service.py`
`register` L80–108, `login` L177–229, `create_session` L147–160.

```mermaid
sequenceDiagram
  autonumber
  participant B as Browser (AuthPages.tsx)
  participant M as SecurityMiddleware
  participant A as auth.py router
  participant S as auth_service
  participant DB as PostgreSQL
  participant E as Email (background task)

  B->>M: POST /api/v1/auth/register {email, password, display_name, consent}<br/>headers: X-Requested-With, Origin
  M->>M: reject if Origin not allowed or header missing (403)
  M->>A: forward
  A->>S: register(...)
  S->>S: rate limit REGISTER_IP · consent required · password policy
  S->>S: Argon2id hash (computed before lookup → equal timing)
  S->>DB: SELECT user by email
  alt new email
    S->>DB: INSERT users, consents(profile_processing), student_profiles, auth_tokens(verify_email digest), audit_events
  else existing email
    S->>DB: INSERT audit_events (failure, email_in_use)
  end
  S-->>A: outcome (never shown to client)
  A-->>B: 202 "If this address can be registered…" (identical either way)
  A--)E: send verification OR "account exists" e-mail after the response

  B->>A: POST /api/v1/auth/login {email, password}
  A->>S: login(...)
  S->>S: rate limits LOGIN_IP + LOGIN_ACCOUNT
  S->>DB: SELECT user FOR NO KEY UPDATE
  S->>S: locked? → generic 401 · verify Argon2id · count failures · exponential lockout
  alt MFA enabled
    S->>DB: INSERT auth_tokens(mfa_challenge digest)
    A-->>B: {status: "mfa_required", mfa_challenge}
  else
    S->>DB: INSERT user_sessions(token_hash, csrf_hash, expires_at) · audit
    A-->>B: Set-Cookie session (HttpOnly, SameSite=Lax) + csrf (readable, SameSite=Strict); body {me}
  end
```

### 5.2 Updating the digital twin

Code: `backend/app/api/v1/twin.py` `rate_skill` L214, `_commit_change` L97–99;
`backend/app/services/twin/history.py` `ensure_snapshot` L18–40; `backend/app/deps.py` `get_principal` L79–87.

```mermaid
sequenceDiagram
  autonumber
  participant B as Browser (SkillsSection.tsx)
  participant D as deps.get_principal
  participant T as twin.py router
  participant H as history.ensure_snapshot
  participant DB as PostgreSQL

  B->>T: PUT /api/v1/twin/skills/{skill_id} {rating}<br/>cookie + X-CSRF-Token
  T->>D: resolve Principal
  D->>DB: SELECT user_sessions JOIN users WHERE token_hash = sha256(cookie)
  D->>D: check expiry/idle · verify CSRF digest · set RLS subject = user
  T->>DB: upsert student_skills (user_id = principal.id)
  T->>H: _commit_change(reason)
  H->>DB: load TwinState (profile, skills, evidence, assessments…)
  H->>H: content_hash = SHA-256(canonical JSON)
  alt hash differs from latest snapshot
    H->>DB: INSERT twin_snapshots(version+1, state, 19 features) · UPDATE profile.twin_version
  end
  T->>DB: COMMIT
  T-->>B: updated skill
  B->>B: invalidateTwin() → refetch profile, skills, completeness, gaps…
```

### 5.3 Calculating role matches and readiness

Code: `backend/app/api/v1/career.py` `role_matches` L264, `run_readiness` L144–159;
`backend/app/services/career/gap_engine.py` `analyse_all_roles` L304–316;
`backend/app/services/career/readiness.py` `predict` L69–138, `store_prediction` L162–181.

```mermaid
sequenceDiagram
  autonumber
  participant B as Browser
  participant C as career.py router
  participant P as proficiency.estimate_skills
  participant G as gap_engine
  participant R as readiness.predict
  participant Reg as ModelRegistry (in memory)
  participant DB as PostgreSQL

  B->>C: GET /api/v1/skill-gaps/summary
  C->>DB: load catalogue (cached by fingerprint) + TwinState
  C->>P: estimate each skill from highest-trust evidence
  C->>G: analyse_all_roles(roles, estimates)
  G-->>C: match, match_upper, known_share, gaps with priorities/actions
  C-->>B: ranked roles (not hiring probabilities)

  B->>C: POST /api/v1/readiness/analyse
  C->>C: rate limit EXPENSIVE_USER
  C->>DB: ensure_snapshot → features of the current twin
  C->>R: predict(features)
  R->>Reg: active model?
  alt no verified model
    R-->>C: {available: false, reason}
    C-->>B: "No estimate has been produced."
  else
    R->>R: raw + Platt-calibrated probability · band · SHAP (LinearExplainer) · warnings (synthetic, low info, OOD)
    C->>DB: INSERT predictions(model_version_id, snapshot_id, explanation, warnings, features)
    C-->>B: band, probability (rounded to 5%), explanation, warnings
  end
```

### 5.4 Running a what-if simulation

Code: `backend/app/api/v1/career.py` `run_simulation` L303–306; `backend/app/services/career/simulator.py`
`simulate` L198–281, `apply_changes` L81–174.

```mermaid
sequenceDiagram
  autonumber
  participant B as Browser (SimulatorPage.tsx)
  participant C as career.py router
  participant S as simulator.simulate
  participant DB as PostgreSQL

  B->>C: POST /api/v1/simulations/run {changes, role_ids}
  C->>C: Pydantic validation (ranges, max items, consistency) · rate limit SIMULATION_USER
  C->>S: simulate(user_id, request)
  S->>DB: read catalogue + real TwinState (read-only)
  S->>S: hypothetical = baseline.clone() (deep copy) · apply validated changes · plausibility notes
  S->>S: estimate_skills ×2 · build_features ×2 (same validation)
  S->>S: analyse_role(base) and analyse_role(hyp) for up to 4 roles
  S->>S: predict(base) and predict(hyp) with the same model
  S-->>C: baseline vs hypothetical, changed features, limitations
  C-->>B: result (nothing written to the twin)
  opt Save scenario
    B->>C: POST /api/v1/simulations/scenarios {name, request}
    C->>DB: ensure_snapshot · INSERT what_if_scenarios(changes, result, base_snapshot_id, model_version_id) · audit
  end
```

### 5.5 Asking the Personalized Mentor

Code: `backend/app/api/v1/mentor.py` `ask` L158–292; `backend/app/services/rag/mentor.py` `assemble` L252–280,
`build_messages` L283–289, `sanitize_links` L217–239; `backend/app/services/rag/store.py` `retrieve` L118–159;
`backend/app/services/rag/ollama_client.py` `embed` L84–100, `chat_stream` L103–146.

```mermaid
sequenceDiagram
  autonumber
  participant B as Browser (MentorPage.tsx + lib/sse.ts)
  participant M as mentor.py /ask
  participant Ctx as rag.mentor.assemble
  participant V as Chroma
  participant O as Ollama (local)
  participant DB as PostgreSQL

  B->>M: POST /api/v1/mentor/ask {question, conversation_id?}
  M->>M: length limit · rate limit MENTOR_USER
  M->>O: cached status (/api/tags): models present?
  alt Ollama or models missing
    M-->>B: 503 mentor_unavailable (no answer generated)
  end
  M->>DB: create/own conversation · last 8 complete messages · INSERT user message
  M->>Ctx: assemble(user_id, question, history)
  Ctx->>DB: deterministic student context (profile, skills, gaps, resources, documents, latest prediction, roadmap/scenario by intent)
  Ctx->>O: POST /api/embed "search_query: …"
  Ctx->>V: query kb_global (not flagged) and kb_private (owner_id = user AND not flagged)
  Ctx->>Ctx: keep passages within distance 0.65 · token budgets
  M-->>B: SSE meta {sources, context_sections}
  M->>M: concurrency gate (1 active, queue 4)
  M->>O: POST /api/chat stream=true think=false
  loop for each streamed chunk
    O-->>M: {"message":{"content": delta}}
    M-->>B: SSE delta {text}
  end
  M->>M: sanitize links (catalogue URLs only) · flag unverified percentages
  M->>DB: INSERT assistant message (sanitised text, sources, tokens, latency)
  M-->>B: SSE done {content (sanitised), removed_links, unverified_numbers, truncated}
```

### 5.6 Generating a roadmap

Code: `backend/app/api/v1/planning.py` `generate` L86–96; `backend/app/services/career/roadmap.py`
`generate_roadmap` L227–278, `plan_items` L95–220, `compare_roadmaps` L363–382.

```mermaid
sequenceDiagram
  autonumber
  participant B as Browser (RoadmapPage.tsx)
  participant P as planning.py router
  participant R as roadmap service
  participant DB as PostgreSQL

  B->>P: POST /api/v1/roadmaps/generate {role_id?, hours_per_week?}
  P->>P: rate limit EXPENSIVE_USER
  P->>R: generate_roadmap(user)
  R->>DB: catalogue + TwinState → estimates
  R->>R: analyse_role(target) → actionable gaps
  R->>R: expand unmet prerequisites · priority-aware lexicographic topological sort · effort ranges · weeks
  R->>DB: archive previous active roadmap · INSERT roadmaps, roadmap_items (carry over in-progress/completed), roadmap_events
  P->>DB: audit · COMMIT
  P-->>B: roadmap view (+ comparison_with_previous: added/removed/moved/carried)
```

### 5.7 Mentor verification of student evidence

Code: `backend/app/api/v1/twin.py` `request_verification` L499–510;
`backend/app/api/v1/staff.py` `_accessible_student` L44–57, `verify_item` L196–219, `verification_queue` L261–278.

```mermaid
sequenceDiagram
  autonumber
  participant St as Student browser
  participant T as twin.py
  participant Me as Mentor browser (StaffPage.tsx)
  participant S as staff.py
  participant DB as PostgreSQL

  St->>T: POST /api/v1/twin/verification-requests {item_type, item_id}
  T->>DB: item (owned) → verification_status = 'pending' · audit · snapshot
  Me->>S: GET /api/v1/staff/verification-queue
  S->>DB: linked + consented students → pending projects/experiences/certifications
  Me->>S: POST /api/v1/staff/students/{id}/verify {item_type, item_id, decision}
  S->>DB: mentor_links(mentor, student) exists? consents(student, mentor_sharing) granted? (privileged lookup)
  alt not linked or no consent
    S->>DB: audit (denied, standalone)
    S-->>Me: 404 (does not reveal the student exists)
  else allowed
    S->>S: RLS subject = student
    S->>DB: UPDATE item status, verified_by, verified_at · snapshot · audit · COMMIT
    S-->>Me: "Item marked verified/rejected"
  end
```

The queue doesn't include pending **assessment results**, although `verify_item` accepts `assessment`. See
[15-project-progress-report.md](15-project-progress-report.md).

## 6. Data storage map

| Data | Store | Written by | Isolation |
|---|---|---|---|
| Accounts, sessions, tokens, consents, links, audit | PostgreSQL | auth, privacy, admin services | Code checks (no RLS on these tables) |
| Twin (profile, skills, evidence, assessments, snapshots, labels) | PostgreSQL | twin router, staff router | Code filters on `user_id` **and** RLS |
| Predictions, scenarios, roadmaps, conversations, feedback | PostgreSQL | career, planning, mentor, privacy routers | Code filters **and** RLS |
| Catalogue (skills, roles, resources, assessments) | PostgreSQL | seed, admin | Global reference data |
| Knowledge-base chunks | Chroma `kb_global` | `reindex_global`, admin upload | Readable by all signed-in users |
| Private document chunks | Chroma `kb_private` | document upload | `where owner_id = <session user>` applied before search |
| Uploaded files | Disk `DATA_DIR/uploads/<user_id>/` | documents router | Random names; access via owned document row |
| Readiness model | Disk + `model_versions` row | training pipeline, `deploy-init`, admin activation | SHA-256 verified before load |

## 7. Deployment topologies

| Mode | Front | API | Database | Ollama | Status |
|---|---|---|---|---|---|
| Native development | Vite dev server `localhost:5173` | uvicorn `127.0.0.1:8010` | Compose `db` on `localhost:5433` | Host `127.0.0.1:11434` | **Verified in this audit** (end-to-end 6/6) |
| Container pilot | nginx `127.0.0.1:8080` | `api` container (port 8000, internal network only) | Compose `db` | `host.docker.internal:11434` (compose `extra_hosts: host-gateway`) | **Verified in this audit** (end-to-end 6/6, health ok) |
| Free hosting | Vercel | Render free web service | Neon PostgreSQL 18 | Not available | **NOT VERIFIED** on the real services; local simulation only |
| Production behind TLS | Caddy (`infra/caddy/Caddyfile`) + nginx | `api` container | Managed PostgreSQL | Private GPU host | **NOT VERIFIED** |
