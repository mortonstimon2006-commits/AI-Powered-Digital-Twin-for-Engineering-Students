-- AI Career Guidance App on Neon: run ONCE in the Neon SQL Editor, on database "neondb", as the project owner
-- (neondb_owner). Guide: docs/operations/free-hosting.md
--
-- Creates the least-privilege runtime role. Migrations run as neondb_owner, which therefore owns
-- the tables; the API connects as twinpath_app, which is not the owner and cannot bypass
-- row-level security, so the RLS policies created by the migrations apply to every request.
--
-- Replace PASTE_GENERATED_PASSWORD_HERE with a password you generate locally (see the guide).
-- Do not save the edited file or commit it.

CREATE ROLE twinpath_app LOGIN PASSWORD 'PASTE_GENERATED_PASSWORD_HERE' NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE CONNECTION LIMIT 40;

-- Runtime guard rails for the application role.
ALTER ROLE twinpath_app SET statement_timeout = '15s';
ALTER ROLE twinpath_app SET idle_in_transaction_session_timeout = '30s';
ALTER ROLE twinpath_app SET lock_timeout = '5s';

GRANT CONNECT ON DATABASE neondb TO twinpath_app;
GRANT USAGE ON SCHEMA public TO twinpath_app;
ALTER DEFAULT PRIVILEGES FOR ROLE neondb_owner IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO twinpath_app;
ALTER DEFAULT PRIVILEGES FOR ROLE neondb_owner IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO twinpath_app;

-- Verification: every column after the name must be false.
SELECT r.rolname,
       r.rolsuper,
       r.rolbypassrls,
       pg_has_role('twinpath_app', 'neon_superuser', 'member') AS in_neon_superuser
FROM pg_roles r
WHERE r.rolname = 'twinpath_app';
