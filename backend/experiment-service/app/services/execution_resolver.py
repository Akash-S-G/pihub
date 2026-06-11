from __future__ import annotations

import logging
from typing import Any

from app.manifest.manifest_service import ExperimentManifestService
from app.manifest.models import ExperimentTemplate
from app.models.execution_resolution import (
    CapabilityCheckResponse,
    DeviceCapabilities,
    ExecutionResolutionRequest,
    ExecutionResolutionResponse,
)


logger = logging.getLogger("experiment-service.execution_resolver")


class ManifestNotFoundError(ValueError):
    pass


class ExecutionDefinitionError(ValueError):
    pass


class ExecutionResolverService:
    SENSOR_ALIASES = {
        "light_sensor": "light",
        "light": "light",
    }

    def __init__(self, manifest_service: ExperimentManifestService | None = None) -> None:
        self.manifest_service = manifest_service or ExperimentManifestService()

    def capability_check(self, request: ExecutionResolutionRequest) -> CapabilityCheckResponse:
        template = self._load_template(request.manifest_id)
        execution = self._load_execution(template)
        required_sensors = self._required_sensors(execution)
        available_sensors = self._available_sensors(request.device_capabilities)
        coverage = self._coverage(required_sensors, available_sensors)
        missing = [sensor for sensor in required_sensors if sensor not in available_sensors]
        supported_modes = self._supported_modes(execution)
        recommended_mode, _, _ = self._select_mode(supported_modes, required_sensors, available_sensors)
        return CapabilityCheckResponse(
            coverage=coverage,
            available=[sensor for sensor in required_sensors if sensor in available_sensors],
            missing=missing,
            recommended_mode=recommended_mode,
        )

    def resolve(self, request: ExecutionResolutionRequest) -> ExecutionResolutionResponse:
        logger.info("[EXPERIMENT] RESOLVE_START")
        logger.info("[EXPERIMENT] MANIFEST_ID=%s", request.manifest_id)
        try:
            template = self._load_template(request.manifest_id)
            execution = self._load_execution(template)
            required_sensors = self._required_sensors(execution)
            available_sensors = self._available_sensors(request.device_capabilities)
            coverage = self._coverage(required_sensors, available_sensors)
            missing = [sensor for sensor in required_sensors if sensor not in available_sensors]
            supported_modes = self._supported_modes(execution)
            resolved_mode, fallback_mode, reason = self._select_mode(
                supported_modes,
                required_sensors,
                available_sensors,
            )

            logger.info("[EXPERIMENT] COVERAGE=%s", coverage)
            logger.info("[EXPERIMENT] REQUIRED_SENSORS=%s", required_sensors)
            logger.info("[EXPERIMENT] AVAILABLE_SENSORS=%s", available_sensors)
            logger.info("[EXPERIMENT] RESOLVED_MODE=%s", resolved_mode)
            logger.info("[EXPERIMENT] FALLBACK_MODE=%s", fallback_mode)

            supported = resolved_mode is not None
            if supported:
                logger.info("[EXPERIMENT] RESOLVE_SUCCESS")
            else:
                logger.info("[EXPERIMENT] RESOLVE_FAILED reason=%s", reason)

            return ExecutionResolutionResponse(
                supported=supported,
                resolved_mode=resolved_mode,
                coverage=coverage,
                missing_capabilities=missing,
                reason=reason,
                execution_definition=execution if supported else None,
            )
        except Exception as exc:
            logger.error("[EXPERIMENT] RESOLVE_FAILED error=%s", exc)
            raise

    def _load_template(self, manifest_id: str) -> ExperimentTemplate:
        if not manifest_id.strip():
            raise ManifestNotFoundError("Manifest id is required")

        direct = self.manifest_service.get_template(manifest_id)
        if direct is not None:
            return direct

        template_id = f"{manifest_id}-manifest-template"
        by_template_id = self.manifest_service.get_template(template_id)
        if by_template_id is not None:
            return by_template_id

        for template in self.manifest_service.list_templates():
            if str(template.manifest.get("id") or "") == manifest_id:
                return template
        raise ManifestNotFoundError(f"Manifest not found: {manifest_id}")

    def _load_execution(self, template: ExperimentTemplate) -> dict[str, Any]:
        execution = template.manifest.get("execution")
        if not isinstance(execution, dict):
            raise ExecutionDefinitionError("Execution definition not found")

        validation = self.manifest_service.validate_execution(execution)
        if not validation.valid:
            raise ExecutionDefinitionError("; ".join(validation.errors))
        return execution

    def _supported_modes(self, execution: dict[str, Any]) -> list[str]:
        modes = execution.get("supported_modes", [])
        return [str(mode) for mode in modes if str(mode).strip()]

    def _required_sensors(self, execution: dict[str, Any]) -> list[str]:
        sensors = execution.get("required_sensors", [])
        if not isinstance(sensors, list):
            return []
        return [self._normalize_sensor(str(sensor)) for sensor in sensors if str(sensor).strip()]

    def _available_sensors(self, capabilities: DeviceCapabilities) -> list[str]:
        payload = self._capabilities_payload(capabilities)
        available: set[str] = set()
        for name, enabled in payload.items():
            if enabled is True:
                available.add(self._normalize_sensor(str(name)))
        return sorted(available)

    def _capabilities_payload(self, capabilities: DeviceCapabilities) -> dict[str, Any]:
        if hasattr(capabilities, "model_dump"):
            return capabilities.model_dump()
        return capabilities.dict()

    def _normalize_sensor(self, sensor: str) -> str:
        normalized = sensor.strip().lower().replace("-", "_")
        return self.SENSOR_ALIASES.get(normalized, normalized)

    def _coverage(self, required_sensors: list[str], available_sensors: list[str]) -> float:
        if not required_sensors:
            return 100.0
        available = set(available_sensors)
        matched = sum(1 for sensor in required_sensors if sensor in available)
        return round((matched / len(required_sensors)) * 100, 2)

    def _select_mode(
        self,
        supported_modes: list[str],
        required_sensors: list[str],
        available_sensors: list[str],
    ) -> tuple[str | None, str | None, str]:
        modes = set(supported_modes)
        available = set(available_sensors)
        required = set(required_sensors)
        all_required_available = required.issubset(available)
        some_required_available = bool(required & available)

        if "sensor" in modes and all_required_available:
            return "sensor", None, "all required sensors available"

        if "hybrid" in modes and some_required_available:
            return "hybrid", "hybrid", "partial sensor coverage; hybrid mode selected"

        if "simulation" in modes:
            return "simulation", "simulation", "sensor requirements not satisfied"

        if "observation" in modes:
            return "observation", "observation", "simulation unavailable; observation mode selected"

        return None, None, "no compatible execution mode available"
