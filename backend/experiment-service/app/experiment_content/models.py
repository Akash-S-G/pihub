from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ExperimentCatalogItem(BaseModel):
    id: str
    title: str
    subject: str
    topics: list[str] = Field(default_factory=list)
    difficulty: str
    learning_objectives: list[str] = Field(default_factory=list)
    runtime_profile: str


class ExperimentLearningContent(BaseModel):
    overview: str
    learning_objectives: list[str]
    theory: str
    procedure: list[str]
    expected_results: list[str]
    common_mistakes: list[str]
    real_world_applications: list[str]


class ExperimentCertification(BaseModel):
    experiment_id: str
    certified: bool
    checks: dict[str, bool]
    errors: list[str] = Field(default_factory=list)
    runtime_profile: str


class ChapterExperimentMapping(BaseModel):
    chapter_id: str
    grade: int | None = None
    subject: str | None = None
    chapter: str
    experiments: list[str] = Field(default_factory=list)


class ExperimentPackage(BaseModel):
    manifest: dict[str, Any]
    metadata: dict[str, Any]
    learning_content: ExperimentLearningContent
    questions: list[dict[str, Any]]
    observations: list[dict[str, Any]]
    flashcards: list[dict[str, str]]
    quiz: list[dict[str, Any]]
    glossary: list[dict[str, str]]
    summary: dict[str, str]
    certification: ExperimentCertification
