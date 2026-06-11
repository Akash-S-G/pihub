from __future__ import annotations

from abc import ABC, abstractmethod

from domain.models import ExperimentManifest


class ExperimentRepository(ABC):
    @abstractmethod
    async def get_experiment(self, experiment_id: str) -> ExperimentManifest | None:
        raise NotImplementedError

    @abstractmethod
    async def list_experiments(self) -> list[ExperimentManifest]:
        raise NotImplementedError

    @abstractmethod
    async def save_experiment(self, experiment: ExperimentManifest) -> ExperimentManifest:
        raise NotImplementedError
