"""ML model registry, predictions, what-if scenarios, roadmaps, documents, mentor chat and
feedback."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_col, updated_at_col, uuid_pk


def _user_fk(index: bool = True) -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=index)


# ----------------------------------------------------------------------------- ML


class ModelVersion(Base):
    __tablename__ = "model_versions"
    __table_args__ = (
        CheckConstraint("status IN ('candidate','active','retired')", name="status_valid"),
        # At most one active model per kind.
        Index("uq_model_versions_one_active", "kind", unique=True, postgresql_where=text("status = 'active'")),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, server_default="readiness_classifier")
    algorithm: Mapped[str] = mapped_column(String(48), nullable=False)
    target: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, server_default="candidate")
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False)
    dataset_ref: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    feature_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    artifact_path: Mapped[str] = mapped_column(String(300), nullable=False)
    artifact_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    trained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = created_at_col()
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Prediction(Base):
    __tablename__ = "predictions"
    __table_args__ = (Index("ix_predictions_user_created", "user_id", "created_at"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = _user_fk(index=False)
    model_version_id: Mapped[int] = mapped_column(ForeignKey("model_versions.id", ondelete="RESTRICT"), nullable=False)
    snapshot_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("twin_snapshots.id", ondelete="SET NULL"))
    raw_score: Mapped[float] = mapped_column(Float, nullable=False)
    probability: Mapped[float | None] = mapped_column(Float)
    band: Mapped[str] = mapped_column(String(24), nullable=False)
    explanation: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    warnings: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default="[]")
    features: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = created_at_col()


class WhatIfScenario(Base):
    __tablename__ = "what_if_scenarios"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = _user_fk()
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    base_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("twin_snapshots.id", ondelete="SET NULL"))
    model_version_id: Mapped[int | None] = mapped_column(ForeignKey("model_versions.id", ondelete="SET NULL"))
    changes: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    result: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = created_at_col()


# ----------------------------------------------------------------------------- roadmaps


class Roadmap(Base):
    __tablename__ = "roadmaps"
    __table_args__ = (
        CheckConstraint("status IN ('active','archived')", name="status_valid"),
        CheckConstraint("hours_per_week BETWEEN 1 AND 80", name="hours_range"),
        Index("uq_roadmaps_one_active", "user_id", unique=True, postgresql_where=text("status = 'active'")),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = _user_fk()
    role_id: Mapped[int] = mapped_column(ForeignKey("career_roles.id", ondelete="RESTRICT"), nullable=False)
    role_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, server_default="active")
    hours_per_week: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    generator_version: Mapped[str] = mapped_column(String(16), nullable=False)
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    previous_roadmap_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("roadmaps.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = created_at_col()
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RoadmapItem(Base):
    __tablename__ = "roadmap_items"
    __table_args__ = (
        CheckConstraint("status IN ('not_started','in_progress','completed','skipped')", name="status_valid"),
        CheckConstraint("action IN ('learn','assess','verify','prerequisite')", name="action_valid"),
        CheckConstraint("effort_hours_min > 0 AND effort_hours_max >= effort_hours_min", name="effort_valid"),
        CheckConstraint("target_level BETWEEN 1 AND 4", name="target_level_range"),
        Index("ix_roadmap_items_roadmap_position", "roadmap_id", "position"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    roadmap_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roadmaps.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = _user_fk(index=False)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id", ondelete="RESTRICT"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(14), nullable=False)
    priority_score: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    current_level: Mapped[float | None] = mapped_column(Float)
    target_level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    effort_hours_min: Mapped[int] = mapped_column(Integer, nullable=False)
    effort_hours_max: Mapped[int] = mapped_column(Integer, nullable=False)
    prerequisite_skill_ids: Mapped[list[int]] = mapped_column(ARRAY(Integer), nullable=False, server_default="{}")
    resource_id: Mapped[int | None] = mapped_column(ForeignKey("learning_resources.id", ondelete="SET NULL"))
    exercise: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    completion_criteria: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    status: Mapped[str] = mapped_column(String(12), nullable=False, server_default="not_started")
    week_start: Mapped[int] = mapped_column(Integer, nullable=False)
    week_end: Mapped[int] = mapped_column(Integer, nullable=False)
    user_edited: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    note: Mapped[str] = mapped_column(String(1000), nullable=False, server_default="")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = updated_at_col()


class RoadmapEvent(Base):
    __tablename__ = "roadmap_events"
    __table_args__ = (Index("ix_roadmap_events_user_time", "user_id", "occurred_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = _user_fk(index=False)
    roadmap_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roadmaps.id", ondelete="CASCADE"), nullable=False)
    item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("roadmap_items.id", ondelete="SET NULL"))
    event: Mapped[str] = mapped_column(String(24), nullable=False)
    from_value: Mapped[str | None] = mapped_column(String(40))
    to_value: Mapped[str | None] = mapped_column(String(40))
    occurred_at: Mapped[datetime] = created_at_col()


# ----------------------------------------------------------------------------- documents


class Document(Base):
    """Uploaded file metadata. Files live under DATA_DIR/uploads (never a public static dir)
    and are only served through authorised endpoints."""

    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint("scope IN ('global','private')", name="scope_valid"),
        CheckConstraint("kind IN ('resume','job_description','knowledge')", name="kind_valid"),
        CheckConstraint("status IN ('uploaded','processed','indexed','failed','rejected')", name="status_valid"),
        CheckConstraint("(scope = 'global') = (owner_id IS NULL)", name="scope_owner_consistent"),
        Index("ix_documents_owner_kind", "owner_id", "kind"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    owner_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    scope: Mapped[str] = mapped_column(String(8), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(80), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_path: Mapped[str | None] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(10), nullable=False, server_default="uploaded")
    error: Mapped[str | None] = mapped_column(String(300))
    extracted: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    injection_flags: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retention_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_col()


# ----------------------------------------------------------------------------- mentor


class MentorConversation(Base):
    __tablename__ = "mentor_conversations"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = _user_fk()
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class MentorMessage(Base):
    __tablename__ = "mentor_messages"
    __table_args__ = (
        CheckConstraint("role IN ('user','assistant')", name="role_valid"),
        CheckConstraint("status IN ('complete','error','cancelled','unavailable')", name="status_valid"),
        Index("ix_mentor_messages_conv_created", "conversation_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mentor_conversations.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = _user_fk(index=False)
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sources: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default="[]")
    context_sections: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default="[]")
    model_tag: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(12), nullable=False, server_default="complete")
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = created_at_col()


# ----------------------------------------------------------------------------- feedback


class UserFeedback(Base):
    __tablename__ = "user_feedback"
    __table_args__ = (
        CheckConstraint(
            "target_type IN ('roadmap_item','role_recommendation','mentor_message','prediction',"
            "'resource','gap_analysis','simulation','general')",
            name="target_type_valid",
        ),
        CheckConstraint("rating BETWEEN 1 AND 5", name="rating_range"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = _user_fk()
    target_type: Mapped[str] = mapped_column(String(24), nullable=False)
    target_id: Mapped[str | None] = mapped_column(String(64))
    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    comment: Mapped[str] = mapped_column(String(1000), nullable=False, server_default="")
    created_at: Mapped[datetime] = created_at_col()
