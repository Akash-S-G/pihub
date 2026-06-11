from __future__ import annotations

from abc import ABC, abstractmethod

from domain.models import ExperimentTemplate


class ExperimentTemplateRepository(ABC):
    @abstractmethod
    async def get_template(self, template_id: str) -> ExperimentTemplate | None:
        raise NotImplementedError

    @abstractmethod
    async def list_templates(self) -> list[ExperimentTemplate]:
        raise NotImplementedError
