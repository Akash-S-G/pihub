from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .models import CURRENT_MANIFEST_VERSION, ExperimentTemplate, TemplateCategory


logger = logging.getLogger("experiment-service.manifest")


def _validate_model(model_type, payload):
    if hasattr(model_type, "model_validate"):
        return model_type.model_validate(payload)
    return model_type.parse_obj(payload)


class ManifestTemplateRepository:
    def __init__(self, seed_path: Path | None = None) -> None:
        self.seed_path = seed_path or Path(__file__).resolve().parents[2] / "storage" / "seed_experiments.json"

    def list_templates(self) -> list[ExperimentTemplate]:
        return [_validate_model(ExperimentTemplate, item) for item in self._load_template_payloads()]

    def get_template(self, template_id: str) -> ExperimentTemplate | None:
        for template in self.list_templates():
            if template.template_id == template_id:
                logger.info("[MANIFEST] TEMPLATE_LOADED id=%s", template_id)
                return template
        return None

    def _load_template_payloads(self) -> list[dict[str, Any]]:
        if not self.seed_path.exists():
            return []
        data = json.loads(self.seed_path.read_text(encoding="utf-8"))
        experiments = data.get("experiments", []) if isinstance(data, dict) else []
        return [self._experiment_to_template(experiment) for experiment in experiments if isinstance(experiment, dict)]

    def _experiment_to_template(self, experiment: dict[str, Any]) -> dict[str, Any]:
        manifest = dict(experiment.get("manifest") or {})
        manifest["manifest_version"] = manifest.get("manifest_version", CURRENT_MANIFEST_VERSION)
        manifest["variables"] = experiment.get("variables", [])
        manifest["steps"] = experiment.get("steps", [])
        manifest["visualizations"] = experiment.get("visualizations", [])
        manifest["metadata"] = experiment.get("metadata", {})
        manifest["execution"] = self._execution_for(manifest, experiment)
        category = self._category(str(experiment.get("category") or manifest.get("subject") or "Custom"))
        template_id = f"{manifest.get('id', 'custom')}-manifest-template"
        return {
            "template_id": template_id,
            "template_name": manifest.get("title") or template_id,
            "category": category,
            "manifest": manifest,
            "description": manifest.get("description") or "",
            "version": CURRENT_MANIFEST_VERSION,
        }

    def _execution_for(self, manifest: dict[str, Any], experiment: dict[str, Any]) -> dict[str, Any]:
        experiment_id = str(manifest.get("id") or "experiment")
        variables = [self._variable(variable) for variable in experiment.get("variables", [])]
        objects = self._objects_for(experiment_id, str(manifest.get("topic") or manifest.get("title") or "Experiment"))
        rules = self._rules_for(experiment_id)
        scene = {
            "scene_id": f"{manifest.get('id', 'experiment')}-scene",
            "name": f"{manifest.get('title', 'Experiment')} Scene",
            "description": manifest.get("description"),
            "objects": objects,
            "variables": variables,
            "rules": rules,
            "metadata": {
                "source": "seed_template",
                "frontend_runtime": "PlaygroundScene",
            },
        }
        logger.info("[EXECUTION_SCHEMA] TEMPLATE_UPGRADED id=%s", manifest.get("id"))
        return {
            "supported_modes": self._supported_modes_for(experiment_id, manifest.get("supported_modes", [])),
            "required_sensors": self._required_sensors_for(experiment_id, manifest.get("required_sensors", [])),
            "scene": scene,
            "variables": variables,
            "objects": objects,
            "rules": rules,
        }

    @staticmethod
    def _supported_modes_for(experiment_id: str, supported_modes: Any) -> list[str]:
        modes = [str(mode) for mode in supported_modes if str(mode).strip()] if isinstance(supported_modes, list) else []
        overrides = {
            "pendulum-motion": ["sensor", "simulation", "observation"],
        }
        return overrides.get(experiment_id, modes)

    @staticmethod
    def _required_sensors_for(experiment_id: str, required_sensors: Any) -> list[str]:
        sensors = [str(sensor) for sensor in required_sensors if str(sensor).strip()] if isinstance(required_sensors, list) else []
        overrides = {
            "pendulum-motion": ["accelerometer"],
        }
        return overrides.get(experiment_id, sensors)

    @staticmethod
    def _variable(variable: dict[str, Any]) -> dict[str, Any]:
        name = str(variable.get("name") or "variable")
        return {
            "name": name,
            "type": str(variable.get("type") or "number"),
            "default_value": variable.get("default_value"),
            "min_value": variable.get("min_value"),
            "max_value": variable.get("max_value"),
            "unit": ManifestTemplateRepository._unit_for(name),
            "description": variable.get("description") or f"Configurable variable: {name}",
        }

    @staticmethod
    def _unit_for(name: str) -> str | None:
        lowered = name.lower()
        if "length" in lowered or "height" in lowered:
            return "cm"
        if "mass" in lowered:
            return "g"
        if "angle" in lowered:
            return "degrees"
        if "resistance" in lowered:
            return "ohm"
        if "voltage" in lowered:
            return "volt"
        if "temperature" in lowered:
            return "celsius"
        if "water" in lowered:
            return "ml"
        return None

    @staticmethod
    def _objects_for(experiment_id: str, topic: str) -> list[dict[str, Any]]:
        object_map: dict[str, list[dict[str, Any]]] = {
            "pendulum-motion": [
                {"object_id": "pendulum-bob", "object_type": "sphere", "name": "Pendulum Bob"},
                {"object_id": "pendulum-string", "object_type": "wire", "name": "Pendulum String"},
            ],
            "hookes-law": [
                {"object_id": "spring", "object_type": "spring", "name": "Spring"},
                {"object_id": "load", "object_type": "block", "name": "Load"},
            ],
            "ohms-law": [
                {"object_id": "wire", "object_type": "wire", "name": "Circuit Wire"},
                {"object_id": "resistor", "object_type": "block", "name": "Resistor"},
            ],
            "plant-growth-observation": [
                {"object_id": "plant", "object_type": "plant", "name": "Plant"},
                {"object_id": "container", "object_type": "container", "name": "Container"},
            ],
            "refraction-through-glass": [
                {"object_id": "glass-slab", "object_type": "lens", "name": "Glass Slab"},
                {"object_id": "light-ray", "object_type": "wire", "name": "Light Ray"},
            ],
        }
        base_objects = object_map.get(experiment_id, [{"object_id": "experiment-object", "object_type": "block", "name": topic}])
        return [
            {
                **item,
                "properties": {},
                "metadata": {"source": "manifest_template"},
            }
            for item in base_objects
        ]

    @staticmethod
    def _rules_for(experiment_id: str) -> list[dict[str, Any]]:
        return [
            {
                "rule_id": f"{experiment_id}-record-observation",
                "name": "Record Observation",
                "trigger": "observation_added",
                "condition": {},
                "action": {"type": "store_event"},
                "enabled": True,
            }
        ]

    @staticmethod
    def _category(value: str) -> str:
        normalized = value.lower().replace(" ", "")
        mapping = {
            "physics": TemplateCategory.PHYSICS.value,
            "chemistry": TemplateCategory.CHEMISTRY.value,
            "biology": TemplateCategory.BIOLOGY.value,
            "mathematics": TemplateCategory.MATHEMATICS.value,
            "maths": TemplateCategory.MATHEMATICS.value,
            "geography": TemplateCategory.GEOGRAPHY.value,
            "environmentalscience": TemplateCategory.ENVIRONMENTAL_SCIENCE.value,
        }
        return mapping.get(normalized, TemplateCategory.CUSTOM.value)
