from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TutorContext(BaseModel):
    chapter: list[Any] = Field(default_factory=list)
    concepts: list[Any] = Field(default_factory=list)
    glossary: list[Any] = Field(default_factory=list)
    faq: list[Any] = Field(default_factory=list)
    learning_objectives: list[Any] = Field(default_factory=list)
    retrieval_diagnostics: dict[str, Any] = Field(default_factory=dict)

    @property
    def context_results(self) -> list[Any]:
        return self.chapter


class ExperimentContext(BaseModel):
    experiment_id: str | None = None
    current_variables: dict[str, Any] = Field(default_factory=dict)
    current_observations: list[Any] = Field(default_factory=list)
    active_investigation_step: dict[str, Any] | None = None
    raw_state: dict[str, Any] = Field(default_factory=dict)

    @property
    def has_context(self) -> bool:
        return bool(self.experiment_id or self.current_variables or self.current_observations or self.active_investigation_step)
