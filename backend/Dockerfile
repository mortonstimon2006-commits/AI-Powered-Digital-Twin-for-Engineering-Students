# syntax=docker/dockerfile:1.7
# AI Career Guidance App API image. Build context: repository root (the knowledge base lives in /knowledge).
#   docker build -f backend/Dockerfile -t twinpath-api .
# Base images are pinned by version AND digest; bump deliberately and re-run the test suite.

FROM ghcr.io/astral-sh/uv:0.13.1 AS uv

FROM python:3.12.15-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258 AS build
COPY --from=uv /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
# Runtime dependencies only (no dev tools, no training plotting stack), exactly as locked.
RUN uv sync --frozen --no-dev --no-group train --no-install-project
COPY backend/app ./app
COPY backend/migrations ./migrations
COPY backend/alembic.ini ./alembic.ini

FROM python:3.12.15-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258
RUN groupadd --system --gid 10001 twinpath \
 && useradd --system --uid 10001 --gid twinpath --home-dir /app --shell /usr/sbin/nologin twinpath \
 && mkdir -p /app/var /app/artifacts/models && chown -R twinpath:twinpath /app/var
WORKDIR /app
COPY --from=build --chown=root:root /app /app
COPY --chown=root:root knowledge /knowledge
# Model artifacts shipped with the image (registered at start-up by `app.cli deploy-init` on hosts
# without a separate migration job). docker-compose mounts its own artifact directory over this path.
COPY --chown=root:root backend/artifacts/bundled /app/artifacts/models
COPY --chown=root:root backend/scripts/start-hosted.sh /app/start-hosted.sh
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TWINPATH_ENV=production \
    DATA_DIR=/app/var \
    MODEL_ARTIFACT_DIR=/app/artifacts/models
USER twinpath
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD ["python", "-c", "import urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/live', timeout=4)"]
# One worker per container: the in-process rate limiter and mentor queue assume a single process
# (scale with replicas + a shared rate-limit store; see docs/deployment.md).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*", "--no-server-header"]
