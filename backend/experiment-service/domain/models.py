from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from domain.enums import ExperimentDifficulty, ExperimentExecutionMode, ExperimentStatus


class ExperimentManifest(BaseModel):
    id: str
    title: str
    description: str
    subject: str
    grade: int
    chapter: str | None = None
    topic: str | None = None
    difficulty: ExperimentDifficulty
    supported_modes: list[ExperimentExecutionMode] = Field(default_factory=list)
    required_sensors: list[str] = Field(default_factory=list)
    estimated_duration_minutes: int | None = None
    tags: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ExperimentStep(BaseModel):
    id: str
    title: str
    description: str
    expected_outcome: str | None = None
    order: int


class ExperimentVariable(BaseModel):
    name: str
    type: str
    default_value: Any | None = None
    min_value: float | None = None
    max_value: float | None = None


class ExperimentVisualization(BaseModel):
    id: str
    type: str
    title: str
    configuration: dict[str, Any] = Field(default_factory=dict)


class ExperimentTemplate(BaseModel):
    id: str
    title: str
    category: str
    manifest: ExperimentManifest


class ExperimentRun(BaseModel):
    run_id: str
    experiment_id: str
    student_id: str
    execution_mode: ExperimentExecutionMode
    status: ExperimentStatus
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None


class ExperimentRunEvent(BaseModel):
    event_id: str
    run_id: str
    event_type: str
    timestamp: datetime
    payload: dict[str, Any] = Field(default_factory=dict)


class ExperimentResult(BaseModel):
    result_id: str
    run_id: str
    completion_percentage: float | None = None
    score: float | None = None
    observations: list[Any] = Field(default_factory=list)
    measurements: list[Any] = Field(default_factory=list)
    notes: str | None = None
