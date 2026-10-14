from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    """Request bodies: unknown fields are rejected, strings are stripped."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ApiModel(BaseModel):
    """Response bodies (built from ORM objects)."""

    model_config = ConfigDict(from_attributes=True)


class Message(ApiModel):
    message: str


class Page[T](ApiModel):
    items: list[T]
    total: int
    limit: int
    offset: int


class PageParams(StrictModel):
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0, le=100_000)
