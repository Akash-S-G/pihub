from __future__ import annotations

from pydantic import BaseModel, Field

from domain.enums import ExperimentExecutionMode


class CreateExperimentRunRequest(BaseModel):
    experiment_id: str
    student_id: str
    execution_mode: ExperimentExecutionMode
    configuration: dict[str, object] = Field(default_factory=dict)


class AppendExperimentEventRequest(BaseModel):
    event_type: str
    payload: dict[str, object] = Field(default_factory=dict)


class CompleteExperimentRunRequest(BaseModel):
    completion_percentage: float | None = None
    score: float | None = None
    observations: list[object] = Field(default_factory=list)
    measurements: list[object] = Field(default_factory=list)
    notes: str | None = None
