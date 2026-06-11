from __future__ import annotations

from abc import ABC, abstractmethod

from domain.enums import ExperimentStatus
from domain.models import ExperimentResult, ExperimentRun, ExperimentRunEvent


class ExperimentRunRepository(ABC):
    @abstractmethod
    async def create_run(self, run: ExperimentRun) -> ExperimentRun:
        raise NotImplementedError

    @abstractmethod
    async def get_run(self, run_id: str) -> ExperimentRun | None:
        raise NotImplementedError

    @abstractmethod
    async def list_student_runs(self, student_id: str) -> list[ExperimentRun]:
        raise NotImplementedError

    @abstractmethod
    async def update_run_status(self, run_id: str, status: ExperimentStatus) -> ExperimentRun | None:
        raise NotImplementedError

    @abstractmethod
    async def complete_run(self, run_id: str, result: ExperimentResult) -> ExperimentRun | None:
        raise NotImplementedError


class ExperimentEventRepository(ABC):
    @abstractmethod
    async def append_event(self, event: ExperimentRunEvent) -> ExperimentRunEvent:
        raise NotImplementedError

    @abstractmethod
    async def get_events(self, run_id: str) -> list[ExperimentRunEvent]:
        raise NotImplementedError


class ExperimentResultRepository(ABC):
    @abstractmethod
    async def save_result(self, result: ExperimentResult) -> ExperimentResult:
        raise NotImplementedError

    @abstractmethod
    async def get_result(self, run_id: str) -> ExperimentResult | None:
        raise NotImplementedError
