from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ExperimentGenerationRequest(BaseModel):
    description: str
    grade: int | None = None
    subject: str | None = None
    topic: str | None = None
    difficulty: str | None = None
    supported_modes: list[str] = Field(default_factory=list)
    required_sensors: list[str] = Field(default_factory=list)
    language: str | None = None


class ExperimentGenerationResponse(BaseModel):
    manifest: dict[str, Any]
    valid: bool
    validation_errors: list[str] = Field(default_factory=list)
    validation_warnings: list[str] = Field(default_factory=list)
    compatibility: dict[str, Any] = Field(default_factory=dict)
    audit: dict[str, Any] = Field(default_factory=dict)
    provider: str = "local_manifest_draft"


class ExperimentRefineRequest(BaseModel):
    manifest: dict[str, Any]
    instructions: str


class ExperimentRefineResponse(BaseModel):
    manifest: dict[str, Any]
    valid: bool
    validation_errors: list[str] = Field(default_factory=list)
    validation_warnings: list[str] = Field(default_factory=list)
    compatibility: dict[str, Any] = Field(default_factory=dict)
    audit: dict[str, Any] = Field(default_factory=dict)
    provider: str = "local_manifest_draft"


class ExperimentExplanationRequest(BaseModel):
    manifest: dict[str, Any]


class ExperimentExplanationResponse(BaseModel):
    purpose: str
    variables: list[str] = Field(default_factory=list)
    objects: list[str] = Field(default_factory=list)
    rules: list[str] = Field(default_factory=list)
    supported_modes: list[str] = Field(default_factory=list)
    required_sensors: list[str] = Field(default_factory=list)
    explanation: str
