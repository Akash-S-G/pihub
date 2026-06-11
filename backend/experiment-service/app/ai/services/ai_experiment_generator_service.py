from __future__ import annotations

import logging
import hashlib
import json
from typing import Any

from app.ai.models import (
    ExperimentExplanationRequest,
    ExperimentExplanationResponse,
    ExperimentGenerationRequest,
    ExperimentGenerationResponse,
    ExperimentRefineRequest,
    ExperimentRefineResponse,
)
from app.ai.prompts.experiment_prompts import ExperimentPromptBuilder
from app.ai.services.manifest_repair_service import ManifestRepairService
from app.ai.services.providers import ExperimentManifestProvider, LocalManifestDraftProvider
from app.ai.validators.manifest_safety_validator import ManifestSafetyValidator
from app.manifest.validator import ExperimentManifestValidator
from app.services.manifest_version_service import ManifestVersionService
from app.core.observability import operation_span


logger = logging.getLogger("experiment-service.ai")


class AIExperimentGeneratorService:
    def __init__(
        self,
        provider: ExperimentManifestProvider | None = None,
        prompt_builder: ExperimentPromptBuilder | None = None,
        repair_service: ManifestRepairService | None = None,
        safety_validator: ManifestSafetyValidator | None = None,
        manifest_validator: ExperimentManifestValidator | None = None,
        compatibility_service: ManifestVersionService | None = None,
    ) -> None:
        self.provider = provider or LocalManifestDraftProvider()
        self.prompt_builder = prompt_builder or ExperimentPromptBuilder()
        self.repair_service = repair_service or ManifestRepairService()
        self.safety_validator = safety_validator or ManifestSafetyValidator()
        self.manifest_validator = manifest_validator or ExperimentManifestValidator()
        self.compatibility_service = compatibility_service or ManifestVersionService()

    def generate(self, request: ExperimentGenerationRequest) -> ExperimentGenerationResponse:
        logger.info("[AI_EXPERIMENT] GENERATE_START provider=%s", self.provider.provider_name)
        with operation_span("ai_generate_experiment"):
            prompt = self.prompt_builder.generation_prompt(request)
            draft = self.provider.generate(request, prompt)
            manifest, valid, errors, warnings, compatibility, audit = self._finalize_manifest(draft)
        logger.info("[AI_EXPERIMENT] GENERATE_END valid=%s errors=%s", valid, len(errors))
        return ExperimentGenerationResponse(
            manifest=manifest,
            valid=valid,
            validation_errors=errors,
            validation_warnings=warnings,
            compatibility=compatibility,
            audit=audit,
            provider=self.provider.provider_name,
        )

    def refine(self, request: ExperimentRefineRequest) -> ExperimentRefineResponse:
        logger.info("[AI_EXPERIMENT] REFINE_START provider=%s", self.provider.provider_name)
        with operation_span("ai_refine_experiment"):
            prompt = self.prompt_builder.refinement_prompt(request)
            draft = self.provider.refine(request, prompt)
            manifest, valid, errors, warnings, compatibility, audit = self._finalize_manifest(draft)
        logger.info("[AI_EXPERIMENT] REFINE_END valid=%s errors=%s", valid, len(errors))
        return ExperimentRefineResponse(
            manifest=manifest,
            valid=valid,
            validation_errors=errors,
            validation_warnings=warnings,
            compatibility=compatibility,
            audit=audit,
            provider=self.provider.provider_name,
        )

    def explain(self, request: ExperimentExplanationRequest) -> ExperimentExplanationResponse:
        manifest = self.repair_service.repair(self.safety_validator.sanitize(request.manifest))
        purpose = str(manifest.get("description") or f"Explore {manifest.get('topic', 'the experiment topic')}.")
        variables = [self._named(item, "name") for item in self._list_of_dicts(manifest.get("variables"))]
        objects = [self._named(item, "name") for item in self._list_of_dicts(manifest.get("objects"))]
        rules = [self._named(item, "name") for item in self._list_of_dicts(manifest.get("rules"))]
        supported_modes = [str(mode) for mode in manifest.get("supported_modes", []) if str(mode).strip()]
        required_sensors = [str(sensor) for sensor in manifest.get("required_sensors", []) if str(sensor).strip()]
        explanation = (
            f"{manifest.get('title')} is a {manifest.get('subject')} experiment about {manifest.get('topic')}. "
            f"It supports {', '.join(supported_modes) or 'no declared modes'} mode(s). "
            f"Students observe or configure {', '.join(variables) or 'the provided variables'} "
            f"using {', '.join(objects) or 'the listed experiment objects'}."
        )
        return ExperimentExplanationResponse(
            purpose=purpose,
            variables=variables,
            objects=objects,
            rules=rules,
            supported_modes=supported_modes,
            required_sensors=required_sensors,
            explanation=explanation,
        )

    def _finalize_manifest(
        self, draft: dict[str, Any]
    ) -> tuple[dict[str, Any], bool, list[str], list[str], dict[str, Any], dict[str, Any]]:
        sanitized = self.safety_validator.sanitize(draft)
        repaired = self.repair_service.repair(sanitized)
        removed_fields = self._removed_fields(draft, sanitized)
        added_defaults = sorted(set(repaired.keys()) - set(sanitized.keys()))
        repair_actions = self._repair_actions(sanitized, repaired)
        compatibility = self.compatibility_service.check_compatibility(repaired)
        validation = self.manifest_validator.validate(repaired)
        if not validation.valid:
            repaired = self.repair_service.repair(repaired)
            validation = self.manifest_validator.validate(repaired)
            compatibility = self.compatibility_service.check_compatibility(repaired)
        audit = {
            "generated_manifest_hash": self._hash(repaired),
            "repair_actions": repair_actions,
            "removed_fields": removed_fields,
            "added_defaults": added_defaults,
            "validation_results": {
                "valid": validation.valid,
                "errors": validation.errors,
                "warnings": validation.warnings,
            },
            "compatibility_results": compatibility,
        }
        return repaired, validation.valid, validation.errors, validation.warnings, compatibility, audit

    def _hash(self, manifest: dict[str, Any]) -> str:
        return hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()

    def _removed_fields(self, original: Any, sanitized: Any, prefix: str = "") -> list[str]:
        removed: list[str] = []
        if isinstance(original, dict) and isinstance(sanitized, dict):
            for key, value in original.items():
                path = f"{prefix}.{key}" if prefix else str(key)
                if key not in sanitized:
                    removed.append(path)
                else:
                    removed.extend(self._removed_fields(value, sanitized[key], path))
        elif isinstance(original, list) and isinstance(sanitized, list):
            for index, value in enumerate(original[: len(sanitized)]):
                removed.extend(self._removed_fields(value, sanitized[index], f"{prefix}[{index}]"))
        return removed

    def _repair_actions(self, before: dict[str, Any], after: dict[str, Any]) -> list[str]:
        actions: list[str] = []
        for key, value in after.items():
            if key not in before:
                actions.append(f"added:{key}")
            elif before.get(key) != value:
                actions.append(f"normalized:{key}")
        return actions

    def _list_of_dicts(self, value: Any) -> list[dict[str, Any]]:
        return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []

    def _named(self, item: dict[str, Any], field: str) -> str:
        return str(item.get(field) or item.get("id") or "unnamed")
