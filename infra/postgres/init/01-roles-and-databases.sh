#!/bin/sh
# Bootstraps least-privilege roles for TwinPath. Runs ONCE, on first container start,
# as the bootstrap superuser. The application never connects as a superuser.
#
#   twinpath_owner : owns the schema, runs Alembic migrations (DDL). Not used at request time.
#   twinpath_app   : runtime role. DML only, NOSUPERUSER, NOBYPASSRLS -> row-level security applies.
set -eu

: "${TWINPATH_OWNER_PASSWORD:?TWINPATH_OWNER_PASSWORD must be set}"
: "${TWINPATH_APP_PASSWORD:?TWINPATH_APP_PASSWORD must be set}"
: "${TWINPATH_DATABASES:=twinpath}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres \
  -v owner_pw="$TWINPATH_OWNER_PASSWORD" -v app_pw="$TWINPATH_APP_PASSWORD" <<'EOSQL'
CREATE ROLE twinpath_owner LOGIN PASSWORD :'owner_pw' NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
CREATE ROLE twinpath_app   LOGIN PASSWORD :'app_pw'   NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS
  CONNECTION LIMIT 60;
-- Runtime guard rails for the application role.
ALTER ROLE twinpath_app SET statement_timeout = '15s';
ALTER ROLE twinpath_app SET idle_in_transaction_session_timeout = '30s';
ALTER ROLE twinpath_app SET lock_timeout = '5s';
EOSQL

for db in $TWINPATH_DATABASES; do
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres \
    -c "CREATE DATABASE \"$db\" OWNER twinpath_owner ENCODING 'UTF8';"
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$db" <<EOSQL
REVOKE ALL ON DATABASE "$db" FROM PUBLIC;
GRANT CONNECT, TEMPORARY ON DATABASE "$db" TO twinpath_owner;
GRANT CONNECT ON DATABASE "$db" TO twinpath_app;
ALTER SCHEMA public OWNER TO twinpath_owner;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO twinpath_app;
ALTER DEFAULT PRIVILEGES FOR ROLE twinpath_owner IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO twinpath_app;
ALTER DEFAULT PRIVILEGES FOR ROLE twinpath_owner IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO twinpath_app;
EOSQL
  echo "TwinPath: database $db initialised"
done
