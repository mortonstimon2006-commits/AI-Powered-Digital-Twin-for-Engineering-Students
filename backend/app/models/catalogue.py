"""Administrator-managed reference data: skills, prerequisites, career roles and their
versioned requirement specifications, learning resources and assessment definitions."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, created_at_col, updated_at_col

SKILL_CATEGORIES = (
    "programming",
    "dsa",
    "databases",
    "web",
    "ml_ai",
    "data",
    "cloud_devops",
    "security",
    "professional",
)


class Skill(Base):
    __tablename__ = "skills"
    __table_args__ = (
        CheckConstraint(
            "category IN ('programming','dsa','databases','web','ml_ai','data','cloud_devops','security','professional')",
            name="category_valid",
        ),
        CheckConstraint("kind IN ('concept','technology','practice')", name="kind_valid"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    category: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False, server_default="concept")
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    # Lower-case surface forms used for deterministic resume / job-description extraction.
    aliases: Mapped[list[str]] = mapped_column(ARRAY(String(64)), nullable=False, server_default="{}")
    practice_exercise: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    completion_criteria: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    updated_at: Mapped[datetime] = updated_at_col()


class SkillPrerequisite(Base):
    __tablename__ = "skill_prerequisites"
    __table_args__ = (
        CheckConstraint("skill_id <> prerequisite_id", name="not_self"),
        CheckConstraint("min_level BETWEEN 1 AND 4", name="min_level_range"),
    )

    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True)
    prerequisite_id: Mapped[int] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True, index=True)
    # Proficiency in the prerequisite expected before working on the dependent skill.
    min_level: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="2")


class CareerRole(Base):
    __tablename__ = "career_roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    summary: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    # Provenance of the requirement specification (who wrote it, from what, when).
    source_note: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    updated_at: Mapped[datetime] = updated_at_col()
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))

    requirements: Mapped[list[RoleSkillRequirement]] = relationship(
        back_populates="role", cascade="all, delete-orphan", lazy="selectin"
    )


class RoleSkillRequirement(Base):
    __tablename__ = "role_skill_requirements"
    __table_args__ = (
        CheckConstraint("required_level BETWEEN 1 AND 4", name="level_range"),
        CheckConstraint("importance > 0 AND importance <= 1", name="importance_range"),
        CheckConstraint("evidence_expected IN ('any','project','assessment')", name="evidence_valid"),
    )

    role_id: Mapped[int] = mapped_column(ForeignKey("career_roles.id", ondelete="CASCADE"), primary_key=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id", ondelete="RESTRICT"), primary_key=True, index=True)
    required_level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    importance: Mapped[float] = mapped_column(Float, nullable=False)
    is_core: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    evidence_expected: Mapped[str] = mapped_column(String(16), nullable=False, server_default="any")
    # Requirements sharing an alt_group are alternatives ("one of Python / Java / C++"):
    # the best-covered member satisfies the group.
    alt_group: Mapped[str | None] = mapped_column(String(32))
    rationale: Mapped[str] = mapped_column(Text, nullable=False, server_default="")

    role: Mapped[CareerRole] = relationship(back_populates="requirements")


class RoleVersion(Base):
    """Immutable snapshot of a role specification each time it changes, so every gap analysis
    and roadmap can cite the exact requirement set it was computed against."""

    __tablename__ = "role_versions"
    __table_args__ = (UniqueConstraint("role_id", "version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("career_roles.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    spec: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = created_at_col()
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))


class LearningResource(Base):
    __tablename__ = "learning_resources"
    __table_args__ = (
        CheckConstraint("verification_status IN ('unverified','verified','broken')", name="verification_valid"),
        CheckConstraint("resource_type IN ('documentation','course','book','tutorial','practice','video')", name="type_valid"),
        CheckConstraint("cost IN ('free','freemium','paid')", name="cost_valid"),
        CheckConstraint("level_min BETWEEN 1 AND 4 AND level_max BETWEEN level_min AND 4", name="levels_valid"),
        CheckConstraint("est_hours_min > 0 AND est_hours_max >= est_hours_min", name="hours_valid"),
        CheckConstraint("url ~ '^https://'", name="url_https"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    url: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    resource_type: Mapped[str] = mapped_column(String(16), nullable=False)
    cost: Mapped[str] = mapped_column(String(10), nullable=False, server_default="free")
    level_min: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="1")
    level_max: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="2")
    est_hours_min: Mapped[int] = mapped_column(Integer, nullable=False)
    est_hours_max: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    verification_status: Mapped[str] = mapped_column(String(12), nullable=False, server_default="unverified")
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_http_status: Mapped[int | None] = mapped_column(SmallInteger)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = created_at_col()


class ResourceSkill(Base):
    __tablename__ = "resource_skills"

    resource_id: Mapped[int] = mapped_column(ForeignKey("learning_resources.id", ondelete="CASCADE"), primary_key=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True, index=True)


class Assessment(Base):
    __tablename__ = "assessments"
    __table_args__ = (
        CheckConstraint("kind IN ('coding','quiz','practical','mock_interview','communication','aptitude')", name="kind_valid"),
        CheckConstraint("max_score > 0", name="max_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    max_score: Mapped[float] = mapped_column(Numeric(7, 2), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class AssessmentSkill(Base):
    __tablename__ = "assessment_skills"

    assessment_id: Mapped[int] = mapped_column(ForeignKey("assessments.id", ondelete="CASCADE"), primary_key=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True, index=True)
