from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Metadata(BaseModel):
    grade: int | None = Field(default=None, ge=0)
    subject: str | None = None
    chapter: str | None = None
    topic: str | None = None
    language: str | None = None


class IngestResponse(BaseModel):
    file_name: str
    chunks_created: int
    collection: str
    metadata: Metadata


class SearchRequest(BaseModel):
    query: str
    limit: int = Field(default=5, ge=1, le=50)
    metadata: Metadata | None = None


class ChapterRequest(BaseModel):
    chapter: str
    limit: int = Field(default=5, ge=1, le=50)
    metadata: Metadata | None = None


class SubjectRequest(BaseModel):
    subject: str
    limit: int = Field(default=5, ge=1, le=50)
    metadata: Metadata | None = None


class TextbookIngestRequest(BaseModel):
    file_name: str
    grade: int | None = Field(default=None, ge=0)
    subject: str | None = None
    chapter: str | None = None
    section: str | None = None
    language: str | None = None
    source: str | None = None


class DirectoryIngestRequest(BaseModel):
    directory: str
    recursive: bool = True
    source: str | None = None


class DebugRetrievalRequest(BaseModel):
    query: str
    limit: int = Field(default=5, ge=1, le=50)
    metadata: Metadata | None = None


class ChunkPreview(BaseModel):
    text: str
    metadata: dict[str, Any]


class CurriculumNode(BaseModel):
    name: str
    description: str | None = None
    children: list[dict[str, Any]] = Field(default_factory=list)


class EducationalResource(BaseModel):
    resource_type: Literal["experiment", "simulation", "animation", "diagram", "virtual_lab", "quiz", "html_interactive"]
    topic: str
    grade_range: list[int] = Field(default_factory=list)
    offline_supported: bool = True
    interactive: bool = False
    source: str | None = None
    url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PackManifest(BaseModel):
    pack_id: str
    pack_name: str
    version: str
    grade: int | None = None
    subject: str | None = None
    chapter: str | None = None
    language: str | None = None
    file_count: int = 0
    chunk_count: int = 0
    created_at: int | None = None


class PackMetadata(BaseModel):
    grade: int | None = None
    subject: str | None = None
    chapter: str | None = None
    language: str | None = None
    source: str | None = None
    curriculum_topics: list[str] = Field(default_factory=list)
    resource_types: list[str] = Field(default_factory=list)


class ChunkResult(BaseModel):
    id: str
    score: float | None = None
    text: str
    metadata: dict[str, Any]


class SearchResponse(BaseModel):
    query: str
    results: list[ChunkResult]


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded", "error"]
    service: str
    checks: dict[str, Any] = Field(default_factory=dict)
