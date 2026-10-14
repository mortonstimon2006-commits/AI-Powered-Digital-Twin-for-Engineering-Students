# Backup and restore

A backup is not proven until a restore has been tested. The procedure below was executed on 2026-10-14 against
the development database: backup 155 KB, checksum OK, **36 tables restored with identical row counts**.

## What to back up

| Data | Where | How |
|---|---|---|
| PostgreSQL (all application data, RLS policies, audit trail) | `db` volume / managed DB | `infra/scripts/backup.sh` (logical, custom format) or the managed service's PITR |
| Uploaded documents | `apidata` volume → `/app/var/uploads` | volume snapshot / encrypted file backup |
| Vector store | `apidata` → `/app/var/chroma` | optional: it can be rebuilt with `reindex-kb`, and private documents re-index on upload |
| Model artifacts | `backend/artifacts/models` | keep every *activated* artifact (immutable, checksummed) |

## Backup

```bash
sh infra/scripts/backup.sh          # -> backups/twinpath-<UTC>.dump + .sha256
```

Recommended for a pilot: nightly backups kept 14 days, weekly backups kept 8 weeks, and **encrypted at rest** (for
example on an encrypted volume, or `age -r <recipient> file.dump`). Store copies off-host, restrict access to
administrators, and apply the same deletion obligations as live data. A student's deletion request is honoured
in backups as they age out.

## Verify (run after every scheduled backup, or at least weekly)

```bash
sh infra/scripts/restore-check.sh backups/twinpath-<UTC>.dump
```

This checks the checksum, restores into a throwaway database, compares per-table row counts with the source, and
drops the throwaway database. It never touches the live database.

## Disaster recovery (full restore)

1. Provision PostgreSQL 18 and run `infra/postgres/init/01-roles-and-databases.sh` to create the roles and an empty
   database owned by `twinpath_owner`.
2. Restore the schema and data:
   `pg_restore -U twinpath_owner -d twinpath --no-owner --exit-on-error < dump`
3. Re-apply the runtime grants, because dumps are taken with `--no-privileges`. RLS policies are part of the
   schema and are restored automatically:
   `psql -U postgres -d twinpath -f infra/postgres/grants.sql`
4. Restore the upload volume, then run `python -m app.cli reindex-kb`.
5. Verify: `/api/v1/health/ready`, sign in with a test account, open a student's twin as an assigned mentor, and
   compare row counts with the backup report.

Expected recovery-point objective: up to 24 h with nightly dumps (use managed PITR for less). Expected
recovery-time objective: under 1 h for pilot-scale data.
