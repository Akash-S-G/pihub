from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ExperimentStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class CreateBuilderManifestRequest(BaseModel):
    owner_id: str
    title: str
    manifest: dict[str, Any]


class UpdateBuilderManifestRequest(BaseModel):
    owner_id: str | None = None
    title: str | None = None
    manifest: dict[str, Any]


class BuilderManifestSummary(BaseModel):
    manifest_id: str
    owner_id: str | None = None
    title: str
    description: str | None = None
    subject: str | None = None
    status: ExperimentStatus
    manifest_version: str
    current_revision: int
    content_hash: str | None = None
    manifest_hash: str | None = None
    created_at: str
    updated_at: str
    tags: list[str] = Field(default_factory=list)


class BuilderManifestDetail(BuilderManifestSummary):
    manifest: dict[str, Any]
    execution: dict[str, Any] | None = None


class BuilderManifestMutationResponse(BaseModel):
    manifest_id: str
    revision: int
    status: ExperimentStatus


class BuilderManifestRevisionSummary(BaseModel):
    id: str
    manifest_id: str
    revision: int
    revision_hash: str | None = None
    created_at: str
    created_by: str | None = None


class BuilderManifestRevisionDetail(BuilderManifestRevisionSummary):
    manifest: dict[str, Any]
    execution: dict[str, Any] | None = None
