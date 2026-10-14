#!/usr/bin/env sh
# Proves a backup is usable: restores it into a throwaway database, compares per-table row counts
# with the source database, and drops the throwaway database. Never touches the live database.
#   sh infra/scripts/restore-check.sh backups/twinpath-<stamp>.dump
set -eu
DUMP="${1:?usage: restore-check.sh <dump file>}"
SOURCE_DB="${SOURCE_DB:-twinpath}"
CHECK_DB="restore_check_$(date -u +%Y%m%d%H%M%S)"
PSQL="docker compose exec -T db psql -U postgres -v ON_ERROR_STOP=1 -qAt"

if [ -f "$DUMP.sha256" ] && command -v sha256sum >/dev/null 2>&1; then
  sha256sum -c "$DUMP.sha256"
fi
$PSQL -d postgres -c "CREATE DATABASE \"$CHECK_DB\""
cleanup() { $PSQL -d postgres -c "DROP DATABASE IF EXISTS \"$CHECK_DB\"" >/dev/null; }
trap cleanup EXIT

docker compose exec -T db pg_restore -U postgres -d "$CHECK_DB" --no-owner --no-privileges --exit-on-error < "$DUMP"

COUNT_SQL="SELECT string_agg(t || '=' || n, ' ' ORDER BY t) FROM (
  SELECT c.relname AS t, (xpath('/row/c/text()', query_to_xml(format('SELECT count(*) AS c FROM %I.%I', n.nspname, c.relname), false, true, '')))[1]::text::int AS n
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE n.nspname = 'public' AND c.relkind = 'r') s;"
SRC="$($PSQL -d "$SOURCE_DB" -c "$COUNT_SQL")"
DST="$($PSQL -d "$CHECK_DB" -c "$COUNT_SQL")"
if [ "$SRC" = "$DST" ]; then
  echo "RESTORE CHECK PASSED: $(echo "$DST" | wc -w) tables, identical row counts"
  echo "$DST" | tr ' ' '\n' | grep -E '^(users|student_profiles|twin_snapshots|predictions|roadmaps|skills|career_roles|model_versions)=' || true
else
  echo "RESTORE CHECK FAILED: row counts differ"
  echo "source:   $SRC"
  echo "restored: $DST"
  exit 1
fi
