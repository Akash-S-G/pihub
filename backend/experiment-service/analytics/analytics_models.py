from __future__ import annotations

from pydantic import BaseModel


class StudentExperimentStats(BaseModel):
    student_id: str
    total_runs: int = 0
    completed_runs: int = 0
    failed_runs: int = 0
    active_runs: int = 0
    average_score: float | None = None
    average_completion: float | None = None
    average_duration_ms: float | None = None
    total_time_spent_ms: int = 0


class ExperimentStats(BaseModel):
    experiment_id: str
    total_runs: int = 0
    completed_runs: int = 0
    failed_runs: int = 0
    average_score: float | None = None
    average_completion: float | None = None
    average_duration_ms: float | None = None
    unique_students: int = 0


class SystemExperimentStats(BaseModel):
    total_runs: int = 0
    completed_runs: int = 0
    failed_runs: int = 0
    active_runs: int = 0
    total_students: int = 0
    total_experiments: int = 0
    average_score: float | None = None
    average_completion: float | None = None
    average_duration_ms: float | None = None
    total_events: int = 0
    total_results: int = 0


class TopExperiment(BaseModel):
    experiment_id: str
    run_count: int = 0
    completion_rate: float = 0.0
    average_score: float | None = None
