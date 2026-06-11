from __future__ import annotations

import logging
from typing import Any

from .models import CURRENT_MANIFEST_VERSION, ValidationResult


logger = logging.getLogger("experiment-service.manifest")


class ExperimentManifestValidator:
    REQUIRED_MANIFEST_FIELDS = (
        "manifest_version",
        "id",
        "title",
        "subject",
        "topic",
        "supported_modes",
        "difficulty",
        "variables",
        "metadata",
    )

    VALID_DIFFICULTIES = {"easy", "medium", "hard"}
    VALID_MODES = {"sensor", "simulation", "hybrid", "observation"}
    VALID_SENSORS = {
        "accelerometer",
        "gyroscope",
        "magnetometer",
        "gps",
        "camera",
        "microphone",
        "barometer",
        "light",
        "timer",
        "ruler",
        "weights",
        "voltmeter",
        "ammeter",
        "protractor",
    }

    def validate(self, manifest: dict[str, Any]) -> ValidationResult:
        logger.info("[MANIFEST] VALIDATION_START")
        errors: list[str] = []
        warnings: list[str] = []
        if not isinstance(manifest, dict):
            logger.info("[MANIFEST] VALIDATION_FAILED")
            return ValidationResult(valid=False, errors=["Manifest must be an object"], manifest_version=None)

        for field in self.REQUIRED_MANIFEST_FIELDS:
            if field not in manifest:
                errors.append(f"Missing required field: {field}")

        manifest_version = manifest.get("manifest_version")
        if manifest_version != CURRENT_MANIFEST_VERSION:
            warnings.append(f"Manifest version {manifest_version!r} differs from current version {CURRENT_MANIFEST_VERSION}")

        for field in ("id", "title", "subject", "topic"):
            value = manifest.get(field)
            if value is not None and not str(value).strip():
                errors.append(f"{field} must not be empty")

        difficulty = manifest.get("difficulty")
        if difficulty is not None and difficulty not in self.VALID_DIFFICULTIES:
            errors.append(f"difficulty must be one of: {sorted(self.VALID_DIFFICULTIES)}")

        supported_modes = manifest.get("supported_modes")
        if supported_modes is not None:
            if not isinstance(supported_modes, list) or not supported_modes:
                errors.append("supported_modes must be a non-empty list")
            else:
                invalid_modes = [mode for mode in supported_modes if mode not in self.VALID_MODES]
                if invalid_modes:
                    errors.append(f"unsupported execution modes: {invalid_modes}")

        variables = manifest.get("variables")
        errors.extend(self._validate_variables(variables, "variables"))

        metadata = manifest.get("metadata")
        if metadata is not None and not isinstance(metadata, dict):
            errors.append("metadata must be an object")

        execution = manifest.get("execution")
        if execution is not None:
            execution_result = self.validate_execution(execution)
            errors.extend(execution_result.errors)
            warnings.extend(execution_result.warnings)
        else:
            warnings.append("execution definition is recommended for package generation")

        errors.extend(self._validate_semantics(manifest))

        valid = not errors
        logger.info("[MANIFEST] VALIDATION_SUCCESS" if valid else "[MANIFEST] VALIDATION_FAILED")
        return ValidationResult(
            valid=valid,
            errors=errors,
            warnings=warnings,
            manifest_version=str(manifest_version) if manifest_version is not None else None,
        )

    def validate_execution(self, execution: dict[str, Any]) -> ValidationResult:
        logger.info("[EXECUTION_SCHEMA] VALIDATION_START")
        errors: list[str] = []
        warnings: list[str] = []
        if not isinstance(execution, dict):
            logger.info("[EXECUTION_SCHEMA] VALIDATION_FAILED")
            return ValidationResult(valid=False, errors=["execution must be an object"], manifest_version=None)

        supported_modes = execution.get("supported_modes")
        if not isinstance(supported_modes, list) or not supported_modes:
            errors.append("execution.supported_modes must be a non-empty list")
        else:
            invalid_modes = [mode for mode in supported_modes if mode not in self.VALID_MODES]
            if invalid_modes:
                errors.append(f"execution.supported_modes contains unsupported modes: {invalid_modes}")

        required_sensors = execution.get("required_sensors", [])
        if not isinstance(required_sensors, list):
            errors.append("execution.required_sensors must be a list")
        else:
            unknown_sensors = [sensor for sensor in required_sensors if sensor not in self.VALID_SENSORS]
            if unknown_sensors:
                warnings.append(f"Unknown sensor requirements: {unknown_sensors}")

        errors.extend(self._validate_variables(execution.get("variables", []), "execution.variables"))
        errors.extend(self._validate_objects(execution.get("objects", []), "execution.objects"))
        errors.extend(self._validate_rules(execution.get("rules", []), "execution.rules"))

        scene_result = self.validate_scene(execution.get("scene"))
        errors.extend(scene_result.errors)
        warnings.extend(scene_result.warnings)
        errors.extend(self._validate_execution_semantics(execution))

        valid = not errors
        logger.info("[EXECUTION_SCHEMA] VALIDATION_SUCCESS" if valid else "[EXECUTION_SCHEMA] VALIDATION_FAILED")
        return ValidationResult(valid=valid, errors=errors, warnings=warnings, manifest_version=None)

    def _validate_semantics(self, manifest: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        variables = manifest.get("variables")
        if isinstance(variables, list):
            errors.extend(self._duplicate_names(variables, "name", "variables"))
            if not variables:
                errors.append("variables must not be empty")
        rules = manifest.get("rules")
        if isinstance(rules, list) and not rules:
            errors.append("rules must not be empty")
        scene = manifest.get("scene")
        if isinstance(scene, dict) and not scene:
            errors.append("scene must not be empty")
        execution = manifest.get("execution")
        if isinstance(execution, dict) and not execution:
            errors.append("execution must not be empty")
        return errors

    def _validate_execution_semantics(self, execution: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        modes = set(execution.get("supported_modes") if isinstance(execution.get("supported_modes"), list) else [])
        sensors = execution.get("required_sensors") if isinstance(execution.get("required_sensors"), list) else []
        if sensors and modes == {"simulation"}:
            errors.append("sensor requirements are incompatible with simulation-only execution")
        variables = execution.get("variables")
        if isinstance(variables, list):
            if not variables:
                errors.append("execution.variables must not be empty")
            errors.extend(self._duplicate_names(variables, "name", "execution.variables"))
        objects = execution.get("objects")
        if isinstance(objects, list):
            errors.extend(self._duplicate_names(objects, "object_id", "execution.objects"))
        rules = execution.get("rules")
        if isinstance(rules, list):
            if not rules:
                errors.append("execution.rules must not be empty")
            errors.extend(self._duplicate_names(rules, "rule_id", "execution.rules"))
        return errors

    def _duplicate_names(self, items: list[Any], field: str, prefix: str) -> list[str]:
        seen: set[str] = set()
        duplicates: list[str] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            value = str(item.get(field) or "").strip().lower()
            if not value:
                continue
            if value in seen:
                duplicates.append(value)
            seen.add(value)
        return [f"{prefix} contains duplicate {field}: {value}" for value in sorted(set(duplicates))]

    def validate_scene(self, scene: dict[str, Any] | None) -> ValidationResult:
        errors: list[str] = []
        warnings: list[str] = []
        if not isinstance(scene, dict):
            return ValidationResult(valid=False, errors=["scene must be an object"], manifest_version=None)
        for field in ("scene_id", "name"):
            if not scene.get(field):
                errors.append(f"scene.{field} is required")
        errors.extend(self._validate_objects(scene.get("objects", []), "scene.objects"))
        errors.extend(self._validate_variables(scene.get("variables", []), "scene.variables"))
        errors.extend(self._validate_rules(scene.get("rules", []), "scene.rules"))
        metadata = scene.get("metadata", {})
        if metadata is not None and not isinstance(metadata, dict):
            errors.append("scene.metadata must be an object")
        valid = not errors
        if valid:
            logger.info("[EXECUTION_SCHEMA] SCENE_VALIDATED")
        return ValidationResult(valid=valid, errors=errors, warnings=warnings, manifest_version=None)

    def _validate_variables(self, variables: Any, prefix: str) -> list[str]:
        errors: list[str] = []
        if variables is None:
            return errors
        if not isinstance(variables, list):
            return [f"{prefix} must be a list"]
        for index, variable in enumerate(variables):
            if not isinstance(variable, dict):
                errors.append(f"{prefix}[{index}] must be an object")
                continue
            if not variable.get("name"):
                errors.append(f"{prefix}[{index}].name is required")
            if not variable.get("type"):
                errors.append(f"{prefix}[{index}].type is required")
        return errors

    def _validate_objects(self, objects: Any, prefix: str) -> list[str]:
        errors: list[str] = []
        if objects is None:
            return errors
        if not isinstance(objects, list):
            return [f"{prefix} must be a list"]
        for index, item in enumerate(objects):
            if not isinstance(item, dict):
                errors.append(f"{prefix}[{index}] must be an object")
                continue
            for field in ("object_id", "object_type", "name"):
                if not item.get(field):
                    errors.append(f"{prefix}[{index}].{field} is required")
            if item.get("properties") is not None and not isinstance(item.get("properties"), dict):
                errors.append(f"{prefix}[{index}].properties must be an object")
            if item.get("metadata") is not None and not isinstance(item.get("metadata"), dict):
                errors.append(f"{prefix}[{index}].metadata must be an object")
        return errors

    def _validate_rules(self, rules: Any, prefix: str) -> list[str]:
        errors: list[str] = []
        if rules is None:
            return errors
        if not isinstance(rules, list):
            return [f"{prefix} must be a list"]
        for index, rule in enumerate(rules):
            if not isinstance(rule, dict):
                errors.append(f"{prefix}[{index}] must be an object")
                continue
            for field in ("rule_id", "name", "trigger"):
                if not rule.get(field):
                    errors.append(f"{prefix}[{index}].{field} is required")
            if rule.get("condition") is not None and not isinstance(rule.get("condition"), dict):
                errors.append(f"{prefix}[{index}].condition must be an object")
            if rule.get("action") is not None and not isinstance(rule.get("action"), dict):
                errors.append(f"{prefix}[{index}].action must be an object")
            if rule.get("enabled") is not None and not isinstance(rule.get("enabled"), bool):
                errors.append(f"{prefix}[{index}].enabled must be a boolean")
        return errors
