"""row-level security policies and least-privilege grants

Defence in depth: even if an application query forgets an ownership filter, PostgreSQL
returns/accepts only rows whose user_id matches the transaction-local `app.user_id`
(set by app.db on every transaction), unless `app.privileged` is 'on' for an operation
that application code has already authorised.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-14
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "twinpath_app"

OWNER_TABLES = (
    "student_profiles", "student_role_preferences", "student_skills", "projects", "experiences",
    "certifications", "assessment_results", "skill_evidence", "twin_snapshots", "readiness_labels",
    "predictions", "what_if_scenarios", "roadmaps", "roadmap_items", "roadmap_events",
    "mentor_conversations", "mentor_messages", "user_feedback", "consents",
)

SUBJECT = "NULLIF(current_setting('app.user_id', true), '')::uuid"
PRIVILEGED = "current_setting('app.privileged', true) = 'on'"


def upgrade() -> None:
    for table in OWNER_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_owner ON {table} "
            f"USING (user_id = {SUBJECT} OR {PRIVILEGED}) "
            f"WITH CHECK (user_id = {SUBJECT} OR {PRIVILEGED})"
        )

    # Documents: global knowledge-base documents are readable by everyone; private ones only
    # by their owner. Only privileged (admin) operations may write global documents.
    op.execute("ALTER TABLE documents ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY documents_read ON documents FOR SELECT "
        f"USING (scope = 'global' OR owner_id = {SUBJECT} OR {PRIVILEGED})"
    )
    op.execute(
        "CREATE POLICY documents_write ON documents FOR ALL "
        f"USING (owner_id = {SUBJECT} OR {PRIVILEGED}) "
        f"WITH CHECK (owner_id = {SUBJECT} OR {PRIVILEGED})"
    )

    # Least privilege for the runtime role (only if it exists — e.g. absent in throwaway DBs).
    op.execute(
        f"""
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {APP_ROLE};
            GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {APP_ROLE};
            -- Audit trail is append-only for the application.
            REVOKE UPDATE, DELETE, TRUNCATE ON audit_events FROM {APP_ROLE};
            -- Migration bookkeeping is not the application's business.
            REVOKE ALL ON alembic_version FROM {APP_ROLE};
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS documents_read ON documents")
    op.execute("DROP POLICY IF EXISTS documents_write ON documents")
    op.execute("ALTER TABLE documents DISABLE ROW LEVEL SECURITY")
    for table in OWNER_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_owner ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
