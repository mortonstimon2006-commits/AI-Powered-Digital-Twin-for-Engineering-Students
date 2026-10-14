"""The student digital twin: profile, skills, practical evidence, assessments, versioned
snapshots, and assessor readiness labels (the supervised target for the ML model)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_col, updated_at_col, uuid_pk

VERIFICATION_CHECK = "verification_status IN ('unverified','pending','verified','rejected')"


def _user_fk(index: bool = True) -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=index)


class StudentProfile(Base):
    __tablename__ = "student_profiles"
    __table_args__ = (
        CheckConstraint("current_semester IS NULL OR current_semester BETWEEN 1 AND 12", name="semester_range"),
        CheckConstraint("graduation_year IS NULL OR graduation_year BETWEEN 2000 AND 2100", name="grad_year_range"),
        CheckConstraint("cgpa IS NULL OR (cgpa >= 0 AND cgpa <= 10)", name="cgpa_range"),
        CheckConstraint("attendance_pct IS NULL OR (attendance_pct >= 0 AND attendance_pct <= 100)", name="attendance_range"),
        CheckConstraint("weekly_hours BETWEEN 1 AND 80", name="weekly_hours_range"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    degree: Mapped[str | None] = mapped_column(String(80))
    specialization: Mapped[str | None] = mapped_column(String(80))
    current_semester: Mapped[int | None] = mapped_column(SmallInteger)
    graduation_year: Mapped[int | None] = mapped_column(SmallInteger)
    cgpa: Mapped[float | None] = mapped_column(Numeric(4, 2))
    # Only stored when the `attendance_data` consent is granted.
    attendance_pct: Mapped[float | None] = mapped_column(Numeric(5, 2))
    academic_achievements: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    headline: Mapped[str] = mapped_column(String(160), nullable=False, server_default="")
    career_interests: Mapped[list[str]] = mapped_column(ARRAY(String(60)), nullable=False, server_default="{}")
    learning_preferences: Mapped[list[str]] = mapped_column(ARRAY(String(24)), nullable=False, server_default="{}")
    weekly_hours: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="8")
    target_role_id: Mapped[int | None] = mapped_column(ForeignKey("career_roles.id", ondelete="SET NULL"))
    twin_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    onboarding_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class StudentRolePreference(Base):
    __tablename__ = "student_role_preferences"
    __table_args__ = (CheckConstraint("rank BETWEEN 1 AND 5", name="rank_range"),)

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("career_roles.id", ondelete="CASCADE"), primary_key=True)
    rank: Mapped[int] = mapped_column(SmallInteger, nullable=False)


class StudentSkill(Base):
    """Self-reported proficiency. Absence of a row means UNKNOWN — never zero."""

    __tablename__ = "student_skills"
    __table_args__ = (
        UniqueConstraint("user_id", "skill_id"),
        CheckConstraint("self_rating BETWEEN 0 AND 4", name="rating_range"),
        CheckConstraint("source IN ('manual','onboarding','resume')", name="source_valid"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = _user_fk()
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"), nullable=False)
    self_rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    source: Mapped[str] = mapped_column(String(12), nullable=False, server_default="manual")
    updated_at: Mapped[datetime] = updated_at_col()


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint(VERIFICATION_CHECK, name="verification_valid"),
        CheckConstraint("completed_on IS NULL OR started_on IS NULL OR completed_on >= started_on", name="dates_ordered"),
        CheckConstraint("repo_url IS NULL OR repo_url ~ '^https://'", name="repo_https"),
        CheckConstraint("demo_url IS NULL OR demo_url ~ '^https://'", name="demo_https"),
        CheckConstraint("team_size IS NULL OR team_size BETWEEN 1 AND 50", name="team_size_range"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = _user_fk()
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    technologies: Mapped[list[str]] = mapped_column(ARRAY(String(40)), nullable=False, server_default="{}")
    repo_url: Mapped[str | None] = mapped_column(String(300))
    demo_url: Mapped[str | None] = mapped_column(String(300))
    is_deployed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    team_size: Mapped[int | None] = mapped_column(SmallInteger)
    started_on: Mapped[date | None] = mapped_column(Date)
    completed_on: Mapped[date | None] = mapped_column(Date)
    verification_status: Mapped[str] = mapped_column(String(12), nullable=False, server_default="unverified")
    verified_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class Experience(Base):
    __tablename__ = "experiences"
    __table_args__ = (
        CheckConstraint(VERIFICATION_CHECK, name="verification_valid"),
        CheckConstraint("kind IN ('internship','job','research','hackathon','volunteer')", name="kind_valid"),
        CheckConstraint("end_date IS NULL OR end_date >= start_date", name="dates_ordered"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = _user_fk()
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    organization: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date)
    outcome: Mapped[str | None] = mapped_column(String(60))
    verification_status: Mapped[str] = mapped_column(String(12), nullable=False, server_default="unverified")
    verified_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class Certification(Base):
    __tablename__ = "certifications"
    __table_args__ = (
        CheckConstraint(VERIFICATION_CHECK, name="verification_valid"),
        CheckConstraint("credential_url IS NULL OR credential_url ~ '^https://'", name="url_https"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = _user_fk()
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    issuer: Mapped[str] = mapped_column(String(120), nullable=False)
    issued_on: Mapped[date | None] = mapped_column(Date)
    expires_on: Mapped[date | None] = mapped_column(Date)
    credential_url: Mapped[str | None] = mapped_column(String(300))
    verification_status: Mapped[str] = mapped_column(String(12), nullable=False, server_default="unverified")
    verified_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_col()


class AssessmentResult(Base):
    __tablename__ = "assessment_results"
    __table_args__ = (
        CheckConstraint("score >= 0 AND score <= max_score", name="score_range"),
        CheckConstraint("source IN ('mentor_recorded','self_reported','imported')", name="source_valid"),
        CheckConstraint(VERIFICATION_CHECK, name="verification_valid"),
        Index("ix_assessment_results_user_taken", "user_id", "taken_on"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = _user_fk(index=False)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("assessments.id", ondelete="RESTRICT"), nullable=False)
    score: Mapped[float] = mapped_column(Numeric(7, 2), nullable=False)
    max_score: Mapped[float] = mapped_column(Numeric(7, 2), nullable=False)
    taken_on: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    verification_status: Mapped[str] = mapped_column(String(12), nullable=False, server_default="unverified")
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    notes: Mapped[str] = mapped_column(String(1000), nullable=False, server_default="")
    created_at: Mapped[datetime] = created_at_col()


class SkillEvidence(Base):
    """Links a skill to a concrete artefact with the level the student claims it demonstrates.
    Trust comes from the *source's* verification status, not from the claim itself."""

    __tablename__ = "skill_evidence"
    __table_args__ = (
        CheckConstraint("source_type IN ('project','experience','certification')", name="source_type_valid"),
        CheckConstraint("level_demonstrated BETWEEN 1 AND 4", name="level_range"),
        CheckConstraint(
            "(source_type = 'project' AND project_id IS NOT NULL AND experience_id IS NULL AND certification_id IS NULL) OR "
            "(source_type = 'experience' AND experience_id IS NOT NULL AND project_id IS NULL AND certification_id IS NULL) OR "
            "(source_type = 'certification' AND certification_id IS NOT NULL AND project_id IS NULL AND experience_id IS NULL)",
            name="source_consistent",
        ),
        Index("ix_skill_evidence_user_skill", "user_id", "skill_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = _user_fk(index=False)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"), nullable=False)
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    experience_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("experiences.id", ondelete="CASCADE"), index=True)
    certification_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("certifications.id", ondelete="CASCADE"), index=True)
    level_demonstrated: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    note: Mapped[str] = mapped_column(String(500), nullable=False, server_default="")
    created_at: Mapped[datetime] = created_at_col()


class TwinSnapshot(Base):
    """Versioned, content-addressed state of the twin. Used for history, diffs, and to pin
    the exact inputs behind every prediction, label and scenario."""

    __tablename__ = "twin_snapshots"
    __table_args__ = (UniqueConstraint("user_id", "version"), Index("ix_twin_snapshots_user_created", "user_id", "created_at"))

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = _user_fk(index=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    features: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = created_at_col()


class ReadinessLabel(Base):
    """Assessor judgement ('interview-ready' or not) captured against a frozen snapshot.
    This is the supervised target for the readiness model — never inferred automatically."""

    __tablename__ = "readiness_labels"
    __table_args__ = (CheckConstraint("label IN ('ready','not_ready')", name="label_valid"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = _user_fk()
    assessor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    snapshot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("twin_snapshots.id", ondelete="CASCADE"), nullable=False)
    role_id: Mapped[int | None] = mapped_column(ForeignKey("career_roles.id", ondelete="SET NULL"))
    label: Mapped[str] = mapped_column(String(12), nullable=False)
    rubric: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    notes: Mapped[str] = mapped_column(String(1000), nullable=False, server_default="")
    rated_at: Mapped[datetime] = created_at_col()
    is_research_consented: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
