from __future__ import annotations

from enum import StrEnum


class ExperimentExecutionMode(StrEnum):
    SENSOR = "sensor"
    SIMULATION = "simulation"
    HYBRID = "hybrid"
    OBSERVATION = "observation"


class ExperimentStatus(StrEnum):
    CREATED = "created"
    DRAFT = "draft"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class ExperimentDifficulty(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class ExperimentCategory(StrEnum):
    PHYSICS = "Physics"
    CHEMISTRY = "Chemistry"
    BIOLOGY = "Biology"
    MATHEMATICS = "Mathematics"
    ENVIRONMENTAL_SCIENCE = "Environmental Science"
    ELECTRONICS = "Electronics"
    GENERAL_SCIENCE = "General Science"
