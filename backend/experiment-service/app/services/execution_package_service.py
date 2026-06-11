from __future__ import annotations

import logging
from typing import Any

from app.manifest.manifest_service import ExperimentManifestService
from app.models.execution_package import ExecutionPackageRequest, ExecutionPackageResponse
from app.services.execution_resolver import ExecutionDefinitionError, ExecutionResolverService
from app.services.manifest_resolver import ManifestResolver
from app.services.manifest_version_service import ManifestVersionService
from app.core.observability import operation_span


logger = logging.getLogger("experiment-service.execution_package")


class ExecutionPackageBuildError(ValueError):
    pass


class ExecutionPackageService:
    def __init__(
        self,
        manifest_service: ExperimentManifestService | None = None,
        resolver: ExecutionResolverService | None = None,
        manifest_resolver: ManifestResolver | None = None,
        version_service: ManifestVersionService | None = None,
    ) -> None:
        self.manifest_service = manifest_service or ExperimentManifestService()
        self.resolver = resolver or ExecutionResolverService(self.manifest_service)
        self.manifest_resolver = manifest_resolver or ManifestResolver(self.manifest_service)
        self.version_service = version_service or ManifestVersionService()

    def build_package(self, request: ExecutionPackageRequest) -> ExecutionPackageResponse:
        logger.info("[EXPERIMENT] PACKAGE_BUILD_START")
        logger.info("[EXPERIMENT] PACKAGE_MANIFEST=%s", request.manifest_id)
        try:
            with operation_span("build_execution_package", manifest_id=request.manifest_id, revision=request.revision):
                resolved = self.manifest_resolver.resolve(request.manifest_id, request.revision)
                manifest = resolved.manifest
                execution = self._validated_execution(manifest, resolved.execution)
                compatibility = self.version_service.check_compatibility(manifest)
                if not compatibility.get("supported"):
                    raise ExecutionDefinitionError(f"Unsupported manifest version: {compatibility.get('manifest_version')}")
                manifest_validation = self.manifest_service.validate(manifest)
                if not manifest_validation.valid:
                    raise ExecutionDefinitionError("; ".join(manifest_validation.errors))

                resolution = self._resolve_execution(execution, request)
            metadata = self._metadata(manifest)
            metadata["source"] = resolved.source
            if resolved.revision is not None:
                metadata["revision"] = resolved.revision
            if resolved.manifest_hash:
                metadata["manifest_hash"] = resolved.manifest_hash
            if resolved.revision_hash:
                metadata["revision_hash"] = resolved.revision_hash

            logger.info("[EXPERIMENT] PACKAGE_MODE=%s", resolution.resolved_mode)
            logger.info("[EXPERIMENT] PACKAGE_COVERAGE=%s", resolution.coverage)
            logger.info("[EXPERIMENT] PACKAGE_VARIABLES=%s", len(execution.get("variables", [])))
            logger.info("[EXPERIMENT] PACKAGE_OBJECTS=%s", len(execution.get("objects", [])))
            logger.info("[EXPERIMENT] PACKAGE_RULES=%s", len(execution.get("rules", [])))
            logger.info("[EXPERIMENT] PACKAGE_BUILD_SUCCESS")

            return ExecutionPackageResponse(
                manifest_id=str(manifest.get("id") or request.manifest_id),
                manifest_version=str(manifest.get("manifest_version") or "unknown"),
                supported=resolution.supported,
                execution_mode=resolution.resolved_mode,
                coverage=resolution.coverage,
                missing_capabilities=resolution.missing_capabilities,
                metadata=metadata,
                scene=execution.get("scene", {}) if resolution.supported else {},
                variables=execution.get("variables", []) if resolution.supported else [],
                objects=execution.get("objects", []) if resolution.supported else [],
                rules=execution.get("rules", []) if resolution.supported else [],
            )
        except Exception as exc:
            logger.error("[EXPERIMENT] PACKAGE_BUILD_FAILED error=%s", exc)
            raise

    def _validated_execution(self, manifest: dict[str, Any], execution: dict[str, Any] | None) -> dict[str, Any]:
        candidate = execution or manifest.get("execution")
        if not isinstance(candidate, dict):
            raise ExecutionDefinitionError("Execution definition not found")
        validation = self.manifest_service.validate_execution(candidate)
        if not validation.valid:
            raise ExecutionDefinitionError("; ".join(validation.errors))
        return candidate

    def _resolve_execution(self, execution: dict[str, Any], request: ExecutionPackageRequest):
        required_sensors = self.resolver._required_sensors(execution)
        available_sensors = self.resolver._available_sensors(request.device_capabilities)
        coverage = self.resolver._coverage(required_sensors, available_sensors)
        missing = [sensor for sensor in required_sensors if sensor not in available_sensors]
        supported_modes = self.resolver._supported_modes(execution)
        resolved_mode, _, reason = self.resolver._select_mode(supported_modes, required_sensors, available_sensors)
        supported = resolved_mode is not None

        from app.models.execution_resolution import ExecutionResolutionResponse

        return ExecutionResolutionResponse(
            supported=supported,
            resolved_mode=resolved_mode,
            coverage=coverage,
            missing_capabilities=missing,
            reason=reason,
            execution_definition=execution if supported else None,
        )

    def _metadata(self, manifest: dict[str, Any]) -> dict[str, Any]:
        return {
            "title": manifest.get("title"),
            "subject": manifest.get("subject"),
            "difficulty": manifest.get("difficulty"),
            "chapter": manifest.get("chapter"),
            "topic": manifest.get("topic"),
        }
