from __future__ import annotations

import time
from typing import Any

from .models import ExperimentContext


class ExperimentContextProvider:
    """Extracts optional experiment state supplied by the client/session."""

    async def load(self, request: Any, session: Any) -> tuple[ExperimentContext, float]:
        started = time.perf_counter()
        state: dict[str, Any] = {}
        for attr in ("sessionState", "session_state"):
            value = getattr(request, attr, None)
            if isinstance(value, dict):
                state.update(value)

        experiment_state = state.get("experiment_state") or state.get("experimentState") or {}
        if not isinstance(experiment_state, dict):
            experiment_state = {"value": experiment_state}

        context = ExperimentContext(
            experiment_id=str(
                experiment_state.get("experiment_id")
                or experiment_state.get("experimentId")
                or state.get("experiment_id")
                or state.get("experimentId")
                or getattr(session, "experiment_id", None)
                or ""
            )
            or None,
            current_variables=self._dict(experiment_state.get("variables") or experiment_state.get("current_variables")),
            current_observations=self._list(experiment_state.get("observations") or experiment_state.get("current_observations")),
            active_investigation_step=self._optional_dict(experiment_state.get("active_step") or experiment_state.get("activeInvestigationStep")),
            raw_state=experiment_state,
        )
        return context, (time.perf_counter() - started) * 1000

    @staticmethod
    def _dict(value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _optional_dict(value: Any) -> dict[str, Any] | None:
        return value if isinstance(value, dict) else None

    @staticmethod
    def _list(value: Any) -> list[Any]:
        return value if isinstance(value, list) else ([] if value is None else [value])
