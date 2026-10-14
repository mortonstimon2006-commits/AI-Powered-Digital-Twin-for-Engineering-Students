#!/usr/bin/env sh
# Logical backup of the TwinPath database (custom format, compressed) from the compose `db` service.
#   sh infra/scripts/backup.sh                 -> backups/twinpath-<UTC timestamp>.dump (+ .sha256)
# Backups contain personal data: store them encrypted (e.g. on an encrypted volume or with
# `age`/`gpg`), restrict access, and apply the same retention policy as the live data.
set -eu
DB_NAME="${DB_NAME:-twinpath}"
OUT_DIR="${OUT_DIR:-backups}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$OUT_DIR"
chmod 700 "$OUT_DIR" 2>/dev/null || true
FILE="$OUT_DIR/$DB_NAME-$STAMP.dump"
docker compose exec -T db pg_dump -U postgres -d "$DB_NAME" --format=custom --compress=6 --no-owner --no-privileges > "$FILE"
if command -v sha256sum >/dev/null 2>&1; then sha256sum "$FILE" > "$FILE.sha256"; fi
echo "backup written: $FILE ($(wc -c < "$FILE") bytes)"
