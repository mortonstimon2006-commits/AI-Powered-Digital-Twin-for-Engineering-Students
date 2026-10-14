from __future__ import annotations

import re
import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from app.schemas.common import ApiModel, StrictModel

_URL_RE = re.compile(r"^https://[A-Za-z0-9.-]+\.[A-Za-z]{2,}(:\d{2,5})?(/[^\s<>\"']*)?$")
LEARNING_PREFS = ("documentation", "video", "interactive", "project_based", "books", "mentoring")
Verification = Literal["unverified", "pending", "verified", "rejected"]


def _https_url(v: str | None) -> str | None:
    if v in (None, ""):
        return None
    if len(v) > 300 or not _URL_RE.match(v):
        raise ValueError("must be a valid https:// URL")
    return v


def _clean_list(values: list[str], max_len: int) -> list[str]:
    out: list[str] = []
    for v in values:
        v = v.strip()
        if v and len(v) <= max_len and v.lower() not in {o.lower() for o in out}:
            out.append(v)
    return out


class ProfileIn(StrictModel):
    degree: str | None = Field(default=None, max_length=80)
    specialization: str | None = Field(default=None, max_length=80)
    current_semester: int | None = Field(default=None, ge=1, le=12)
    graduation_year: int | None = Field(default=None, ge=2000, le=2100)
    cgpa: float | None = Field(default=None, ge=0, le=10)
    attendance_pct: float | None = Field(default=None, ge=0, le=100)
    academic_achievements: str = Field(default="", max_length=2000)
    headline: str = Field(default="", max_length=160)
    career_interests: list[str] = Field(default_factory=list, max_length=10)
    learning_preferences: list[Literal["documentation", "video", "interactive", "project_based", "books", "mentoring"]] = Field(
        default_factory=list, max_length=6
    )
    weekly_hours: int = Field(default=8, ge=1, le=80)

    @field_validator("career_interests")
    @classmethod
    def _interests(cls, v: list[str]) -> list[str]:
        return _clean_list(v, 60)

    @field_validator("cgpa")
    @classmethod
    def _cgpa_precision(cls, v: float | None) -> float | None:
        return None if v is None else round(v, 2)


class RolePreferencesIn(StrictModel):
    target_role_id: int | None = None
    preferred_role_ids: list[int] = Field(default_factory=list, max_length=5)

    @model_validator(mode="after")
    def _unique(self) -> RolePreferencesIn:
        if len(set(self.preferred_role_ids)) != len(self.preferred_role_ids):
            raise ValueError("preferred_role_ids must be unique")
        return self


class ProfileOut(ApiModel):
    degree: str | None
    specialization: str | None
    current_semester: int | None
    graduation_year: int | None
    cgpa: float | None
    attendance_pct: float | None
    academic_achievements: str
    headline: str
    career_interests: list[str]
    learning_preferences: list[str]
    weekly_hours: int
    target_role_id: int | None
    preferred_role_ids: list[int]
    twin_version: int
    onboarding_completed_at: datetime | None
    attendance_consent: bool


class SkillRatingIn(StrictModel):
    self_rating: int = Field(ge=0, le=4)


class BulkSkillRating(StrictModel):
    skill_id: int
    self_rating: int = Field(ge=0, le=4)


class BulkSkillRatingsIn(StrictModel):
    ratings: list[BulkSkillRating] = Field(max_length=100)
    source: Literal["manual", "onboarding", "resume"] = "manual"


class EvidenceLinkIn(StrictModel):
    skill_id: int
    level: int = Field(ge=1, le=4, description="Level the student claims this artefact demonstrates")
    note: str = Field(default="", max_length=500)


class ProjectIn(StrictModel):
    title: str = Field(min_length=2, max_length=120)
    summary: str = Field(default="", max_length=4000)
    technologies: list[str] = Field(default_factory=list, max_length=20)
    repo_url: str | None = None
    demo_url: str | None = None
    is_deployed: bool = False
    team_size: int | None = Field(default=None, ge=1, le=50)
    started_on: date | None = None
    completed_on: date | None = None
    skills: list[EvidenceLinkIn] = Field(default_factory=list, max_length=20)

    @field_validator("repo_url", "demo_url")
    @classmethod
    def _urls(cls, v: str | None) -> str | None:
        return _https_url(v)

    @field_validator("technologies")
    @classmethod
    def _tech(cls, v: list[str]) -> list[str]:
        return _clean_list(v, 40)

    @model_validator(mode="after")
    def _dates(self) -> ProjectIn:
        if self.started_on and self.completed_on and self.completed_on < self.started_on:
            raise ValueError("completed_on must not be before started_on")
        if self.completed_on and self.completed_on > date.today():
            raise ValueError("completed_on cannot be in the future")
        return self


class ExperienceIn(StrictModel):
    kind: Literal["internship", "job", "research", "hackathon", "volunteer"]
    organization: str = Field(min_length=2, max_length=120)
    title: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=4000)
    start_date: date
    end_date: date | None = None
    outcome: str | None = Field(default=None, max_length=60)
    skills: list[EvidenceLinkIn] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def _dates(self) -> ExperienceIn:
        if self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must not be before start_date")
        if self.start_date > date.today():
            raise ValueError("start_date cannot be in the future")
        return self


class CertificationIn(StrictModel):
    name: str = Field(min_length=2, max_length=160)
    issuer: str = Field(min_length=2, max_length=120)
    issued_on: date | None = None
    expires_on: date | None = None
    credential_url: str | None = None
    skills: list[EvidenceLinkIn] = Field(default_factory=list, max_length=10)

    @field_validator("credential_url")
    @classmethod
    def _url(cls, v: str | None) -> str | None:
        return _https_url(v)


class SelfReportedAssessmentIn(StrictModel):
    assessment_id: int
    score: float = Field(ge=0)
    taken_on: date
    notes: str = Field(default="", max_length=1000)

    @field_validator("taken_on")
    @classmethod
    def _not_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("taken_on cannot be in the future")
        return v


class EvidenceOut(ApiModel):
    id: uuid.UUID
    skill_id: int
    level_demonstrated: int
    note: str


class ProjectOut(ApiModel):
    id: uuid.UUID
    title: str
    summary: str
    technologies: list[str]
    repo_url: str | None
    demo_url: str | None
    is_deployed: bool
    team_size: int | None
    started_on: date | None
    completed_on: date | None
    verification_status: Verification
    skills: list[EvidenceOut] = []
    created_at: datetime


class ExperienceOut(ApiModel):
    id: uuid.UUID
    kind: str
    organization: str
    title: str
    description: str
    start_date: date
    end_date: date | None
    outcome: str | None
    verification_status: Verification
    skills: list[EvidenceOut] = []


class CertificationOut(ApiModel):
    id: uuid.UUID
    name: str
    issuer: str
    issued_on: date | None
    expires_on: date | None
    credential_url: str | None
    verification_status: Verification
    skills: list[EvidenceOut] = []


class AssessmentResultOut(ApiModel):
    id: uuid.UUID
    assessment_id: int
    assessment_name: str
    kind: str
    score: float
    max_score: float
    pct: float
    taken_on: date
    source: str
    verification_status: Verification
    notes: str


class VerificationRequestIn(StrictModel):
    item_type: Literal["project", "experience", "certification", "assessment"]
    item_id: uuid.UUID
