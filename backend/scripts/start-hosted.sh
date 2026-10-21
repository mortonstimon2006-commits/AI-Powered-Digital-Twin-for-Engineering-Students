#!/bin/sh
# Start-up for single-container hosts that have no separate migration job (e.g. Render's free
# plan): migrations (owner role), reference data + shipped models (app role), then the API, all
# in one process. Every step is idempotent, so it is safe on each restart or wake-up.
set -eu
exec python -m app.cli serve-hosted
