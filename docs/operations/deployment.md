# Deployment, environments and rollback

## Environments

| Environment | Purpose | Data | Config highlights |
|---|---|---|---|
| development | local coding | seeded catalogue + throwaway accounts | `TWINPATH_ENV=development`, `EMAIL_BACKEND=file`, Vite proxy |
| test | automated tests/CI | `twinpath_test` DB, truncated per test | set by `tests/conftest.py`; never point at real data |
| staging | pre-release verification | **synthetic or consented test data only** | identical images and config shape to production, https origins |
| production | pilot use | real, consented student data | `TWINPATH_ENV=production` (fails closed on unsafe config), SMTP, TLS everywhere |

Production data must never be copied into development or staging.

## Topologies for the local LLM (choose one)

1. **Single trusted machine (local pilot).** Everything runs on one GPU workstation (the configuration verified in
   this repository: RTX 4060 Laptop 8 GB). Ollama listens on `127.0.0.1:11434` only.
2. **Private-network GPU server.** The web/API host is public (behind TLS), and Ollama runs on a separate GPU
   machine reachable **only** over a private network or VPN (WireGuard/Tailscale), firewalled to the API host's
   address. Ollama has no authentication, so it must never be reachable from the internet.
3. **Fully public cloud hosting without a GPU.** Not supported for the mentor: an 8B model on CPU is too slow.
   The rest of the app works and the mentor reports "unavailable". **Do not** substitute an external LLM API; that
   would violate the local-only requirement.

Ordinary cloud VMs do not provide NVIDIA GPUs. A GPU Ollama host needs a compatible GPU, drivers, and (for
containers) the NVIDIA container toolkit.

## Minimum hardware (measured)

* Mentor: `qwen3:8b` Q4_K_M uses about 5.3 GB VRAM at a 4,096-token context (100% GPU offload). Total GPU use
  was about 7.1 GB of 8.2 GB with other apps. Warm answers take about 5 s; generation runs at about 43 tokens/s;
  prompt processing at about 2,400 tokens/s; cold load 8–22 s. Source: `docs/reports/llm-benchmark.json`.
* API: about 1.5 GB RAM (ML and vector libraries). PostgreSQL: 1 GB RAM minimum for a pilot.
* API cold start takes about 20 s (heavy imports), so give health checks a start period.

## First deployment (container pilot)

```bash
cp .env.example .env            # then fill every secret; set TWINPATH_ENV, origins, SMTP
docker compose up -d db
docker compose --profile app build
docker compose --profile app up -d          # runs migrations + catalogue seed, then api + web
docker compose exec api python -m app.cli create-admin admin@your-institution.edu
docker compose exec api python -m app.cli reindex-kb      # needs Ollama + nomic-embed-text
docker compose exec api python -m app.cli validate-links
```

Model artifacts are mounted read-only from `backend/artifacts/models`. Register and activate a reviewed model
with `uv run python -m ml_pipeline.train ... --activate`, or through Admin → Models.

For staging/production put the Caddy edge (`infra/caddy/Caddyfile`) or an equivalent TLS terminator in front of
`web`. Use a managed PostgreSQL with TLS (`?sslmode=verify-full`) and encryption at rest where available.

## Releases and rollback

1. CI must be green (lint, types, tests, migrations up/down/up + drift check, audits, secret scan, image scan).
2. **Back up the database** (`sh infra/scripts/backup.sh`) and verify the backup (`restore-check.sh`).
3. Deploy new images, then `alembic upgrade head` (the `migrate` service does this).
4. Smoke test: `/api/v1/health/ready`, sign in, open the dashboard, run readiness.

**Rollback:**
* *Application only:* redeploy the previous image tags. All migrations are additive within a release.
* *Schema:* `alembic downgrade <previous revision>`. Every migration has a tested downgrade (CI runs up/down/up).
  If a downgrade would lose data, restore from the pre-release backup instead.
* *Model:* Admin → Models → activate the previous version. Activation re-verifies its checksum, and each estimate
  records the version it used.
* *Role framework:* role versions are immutable snapshots; re-save the previous specification as a new version.

## Monitoring and health

* `GET /api/v1/health/live`: process up (container health check).
* `GET /api/v1/health/ready`: database, readiness model and mentor LLM status (`ok` / `degraded` / `down`, with
  503 only when the database is down).
* Admin → System: Ollama reachability, model tags and quantisation, VRAM of loaded models, mentor queue counters,
  vector-store size and data counts.
* Logs: structured JSON on stdout with request ids, redacted. Ship them to your log platform and alert on
  5xx rate, `auth.login` failure spikes, `staff.access` denials and mentor failures.
