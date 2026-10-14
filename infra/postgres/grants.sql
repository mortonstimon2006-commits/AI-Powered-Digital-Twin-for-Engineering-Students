-- Re-applies least-privilege runtime grants after a restore (dumps are taken with --no-privileges).
-- Run as the schema owner or a superuser:  psql -d twinpath -f infra/postgres/grants.sql
-- Mirrors the grant block of migration 0002; keep the two in sync.
GRANT USAGE ON SCHEMA public TO twinpath_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO twinpath_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO twinpath_app;
REVOKE UPDATE, DELETE, TRUNCATE ON audit_events FROM twinpath_app;
REVOKE ALL ON alembic_version FROM twinpath_app;
ALTER DEFAULT PRIVILEGES FOR ROLE twinpath_owner IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO twinpath_app;
ALTER DEFAULT PRIVILEGES FOR ROLE twinpath_owner IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO twinpath_app;
