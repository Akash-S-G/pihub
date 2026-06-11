from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from domain.models import ExperimentResult, ExperimentRun


class ExperimentRuntime(ABC):
    @abstractmethod
    async def initialize(self, experiment_id: str, configuration: dict[str, Any] | None = None) -> ExperimentRun:
        raise NotImplementedError

    @abstractmethod
    async def start(self, run_id: str) -> ExperimentRun:
        raise NotImplementedError

    @abstractmethod
    async def pause(self, run_id: str) -> ExperimentRun:
        raise NotImplementedError

    @abstractmethod
    async def resume(self, run_id: str) -> ExperimentRun:
        raise NotImplementedError

    @abstractmethod
    async def stop(self, run_id: str) -> ExperimentRun:
        raise NotImplementedError

    @abstractmethod
    async def export_results(self, run_id: str) -> ExperimentResult:
        raise NotImplementedError
