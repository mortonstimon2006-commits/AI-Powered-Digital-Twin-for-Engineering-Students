# TwinPath AI

**An explainable, evidence-aware career digital twin for engineering students**, with a local AI mentor.

TwinPath keeps a versioned record of a student's academics, skills and evidence. It compares that record with
versioned role specifications, estimates assessor-judged interview readiness with a calibrated, explained model,
simulates what-if changes on an isolated copy of the twin, and turns gaps into a prerequisite-ordered roadmap.
A retrieval-augmented mentor runs **entirely locally** through Ollama.

> **Honesty notes.** Match scores are not hiring probabilities. The active readiness model is a **demonstration
> trained on synthetic data** (see [model card](docs/ml/model-card.md)). Nothing here guarantees employment.
> Full status: [docs/status-and-limitations.md](docs/status-and-limitations.md).

## Feature map

| Area | What it does | Docs |
|---|---|---|
| Auth & accounts | Argon2id, server sessions, CSRF, MFA (TOTP), recovery, session management, RBAC (student/mentor/admin), export and hard deletion | [threat model](docs/security/threat-model.md) |
| Digital twin | Academics, skills (0–4), projects/experience/certifications with skill evidence, assessments, verification workflow, snapshots and diffs, completeness | [methodology](docs/methodology/README.md) |
| Readiness model | Logistic regression / RF / XGBoost compared; grouped CV; calibration; SHAP; out-of-distribution warnings; versioned registry | [model card](docs/ml/model-card.md), [dataset card](docs/ml/dataset-card.md) |
| Roles & gaps | 6 versioned roles, 42 skills, configurable gap formula, ranking sensitivity | [role framework](docs/methodology/role-framework.md) |
| What-if simulator | Hypothetical changes on a deep copy using the same pipeline; scenarios saved and compared | methodology §3 |
| Knowledge graph | NetworkX graph with provenance-labelled edges, insights queries, 3D and accessible 2D views | methodology §5 |
| Roadmap | Prerequisite-ordered, time-boxed plan from real gaps; progress; regeneration with diff | methodology §4 |
| AI mentor | Local qwen3:8b + nomic-embed-text, owner-scoped RAG over Chroma, injection filtering, link sanitisation | [RAG evaluation](docs/reports/rag-evaluation.md) |
| Resume & JD | Sandboxed PDF/DOCX/TXT parsing, skill extraction, writing suggestions, JD comparison | — |
| Mentor & admin tools | Consent-gated student overview, verification, assessments, assessor labels; users, roles, resources, models, knowledge base, audit | [API](docs/api/README.md) |

## Requirements

* Windows, macOS or Linux; Docker (Compose v2); Python 3.12; [uv](https://docs.astral.sh/uv/) 0.13; Node 22.12+ (24 tested).
* For the mentor: [Ollama](https://ollama.com) with `qwen3:8b` and `nomic-embed-text`. A GPU with about 6 GB or
  more of free VRAM is recommended (verified on an RTX 4060 Laptop, 8 GB).

## Quick start (native development)

```bash
cp .env.example .env
```

Fill in every placeholder in `.env`; the file explains how to generate each secret. Then start the database:

```bash
docker compose up -d db
```

Backend:

```bash
cd backend
uv sync --frozen
uv run alembic upgrade head
uv run python -m app.cli seed
uv run python -m ml_pipeline.train --source synthetic --seed 42 --activate
uv run python -m app.cli validate-links
uv run uvicorn app.main:app --host 127.0.0.1 --port 8010
```

Local AI (another terminal):

```bash
ollama pull qwen3:8b
```

```bash
ollama pull nomic-embed-text
```

```bash
cd backend && uv run python -m app.cli reindex-kb
```

Frontend (another terminal):

```bash
cd frontend
npm ci
npm run dev
```

Open http://localhost:5173 and register. In development, verification emails are written to
`backend/var/outbox/`. To create an administrator (prompts for a password; an existing account is promoted):

```bash
cd backend && uv run python -m app.cli create-admin you@your-institution.edu
```

## Quick start (containers, local pilot)

```bash
docker compose --profile app up -d --build
```

This runs migrations and the seed, then serves the app at http://localhost:8080. Ollama stays on the host. See the
[deployment guide](docs/operations/deployment.md) for topologies, TLS, environments and rollback.

## Testing

The backend tests use the test database (`TEST_DATABASE_URL`), so `docker compose up -d db` must be running:

```bash
cd backend && uv run pytest -q
```

```bash
cd frontend && npm run lint && npm run typecheck && npm test
```

End-to-end tests need the stack running (dev servers by default; set `E2E_BASE_URL=http://localhost:8080` for
the containers). Each run registers a throwaway account and deletes it. Never point this suite at production.

```bash
cd frontend && npx playwright install chromium
```

```bash
cd frontend && npx playwright test
```

The RAG evaluation needs Ollama with both models. It uses (and truncates) the **test** database from
`TEST_DATABASE_URL`, and writes `docs/reports/rag-eval.{json,md}`:

```bash
cd backend && uv run python -m eval.run_rag_eval
```

| Suite | Result (2026-10-14) |
|---|---|
| Backend (pytest, real PostgreSQL 18, app role + RLS) | 94 passed |
| Frontend (Vitest + Testing Library + axe) | 25 passed |
| End-to-end (Playwright, desktop + mobile) | 6 passed against dev servers **and** against the containers |
| RAG evaluation (local qwen3:8b) | retrieval hit@1 1.00 (24 q) · generation 9/9 scenarios |
| Static checks | ruff, mypy (79 files: app, ML pipeline, eval), ESLint, `tsc --strict`: clean |
| Security scans | gitleaks clean · npm audit 0 · pip-audit 0 after 4 documented, unreachable Chroma-server exceptions |

## Repository layout

```
backend/    FastAPI app, Alembic migrations, ML pipeline, RAG eval, tests (uv.lock)
frontend/   React SPA, Playwright e2e, nginx config (package-lock.json)
knowledge/  authored knowledge-base documents for the mentor
infra/      Postgres bootstrap + grants, Caddy edge config, backup/restore scripts
docs/       architecture, API, methodology, ML cards, security, operations, reports, research, status
```

## Documentation index

[Architecture](docs/architecture.md) · [API](docs/api/README.md) · [Methodology](docs/methodology/README.md) ·
[Model card](docs/ml/model-card.md) · [Dataset card](docs/ml/dataset-card.md) ·
[RAG evaluation](docs/reports/rag-evaluation.md) · [Threat model](docs/security/threat-model.md) ·
[Security checklist](docs/security/checklist.md) ·
[Incident response](docs/security/incident-response.md) · [Deployment & rollback](docs/operations/deployment.md) ·
[Backup & restore](docs/operations/backup-restore.md) · [Research framing](docs/research.md) ·
[Status & limitations](docs/status-and-limitations.md)

## Licences

Application code: choose a licence before publishing. Models: Qwen3 8B and nomic-embed-text are Apache-2.0
(verified via `ollama show`). Fonts: Space Grotesk, Inter and JetBrains Mono are under the SIL Open Font Licence.
Knowledge-base documents in `knowledge/` were written for this project.
