from __future__ import annotations

import re
from typing import Any

from app.manifest.models import CURRENT_MANIFEST_VERSION


class ManifestRepairService:
    VALID_MODES = {"sensor", "simulation", "hybrid", "observation"}
    VALID_DIFFICULTIES = {"easy", "medium", "hard"}

    def repair(self, manifest: dict[str, Any]) -> dict[str, Any]:
        repaired = dict(manifest)
        title = self._clean_text(repaired.get("title")) or "Untitled Experiment"
        topic = self._clean_text(repaired.get("topic")) or title
        subject = self._clean_text(repaired.get("subject")) or "General Science"

        repaired["manifest_version"] = CURRENT_MANIFEST_VERSION
        repaired["id"] = self._slug(repaired.get("id") or title)
        repaired["title"] = title
        repaired["description"] = self._clean_text(repaired.get("description")) or f"Explore {topic} through a guided experiment."
        repaired["subject"] = subject
        repaired["topic"] = topic
        repaired["difficulty"] = self._difficulty(repaired.get("difficulty"))
        repaired["supported_modes"] = self._modes(repaired.get("supported_modes"))
        repaired["required_sensors"] = self._list(repaired.get("required_sensors"))
        repaired["variables"] = self._variables(repaired.get("variables"))
        repaired["objects"] = self._objects(repaired.get("objects"), repaired["id"], topic)
        repaired["rules"] = self._rules(repaired.get("rules"), repaired["id"])
        repaired["scene"] = self._scene(repaired.get("scene"), repaired)
        repaired["metadata"] = self._metadata(repaired.get("metadata"))
        return repaired

    def _metadata(self, metadata: Any) -> dict[str, Any]:
        base = metadata if isinstance(metadata, dict) else {}
        return {
            **base,
            "source": base.get("source") or "ai_experiment_generator",
            "runtime_agnostic": True,
        }

    def _scene(self, scene: Any, manifest: dict[str, Any]) -> dict[str, Any]:
        base = scene if isinstance(scene, dict) else {}
        return {
            "scene_id": self._slug(base.get("scene_id") or f"{manifest['id']}-scene"),
            "name": self._clean_text(base.get("name")) or f"{manifest['title']} Scene",
            "description": self._clean_text(base.get("description")) or manifest["description"],
            "objects": manifest["objects"],
            "variables": manifest["variables"],
            "rules": manifest["rules"],
            "metadata": base.get("metadata") if isinstance(base.get("metadata"), dict) else {},
        }

    def _variables(self, variables: Any) -> list[dict[str, Any]]:
        items = variables if isinstance(variables, list) else []
        normalized: list[dict[str, Any]] = []
        for index, variable in enumerate(items):
            if not isinstance(variable, dict):
                continue
            name = self._slug(variable.get("name") or f"variable_{index + 1}").replace("-", "_")
            normalized.append(
                {
                    "name": name,
                    "type": self._clean_text(variable.get("type")) or "number",
                    "default_value": variable.get("default_value"),
                    "min_value": variable.get("min_value"),
                    "max_value": variable.get("max_value"),
                    "unit": variable.get("unit"),
                    "description": self._clean_text(variable.get("description")) or f"Configurable variable: {name}",
                }
            )
        if normalized:
            return normalized
        return [
            {
                "name": "observation_count",
                "type": "number",
                "default_value": 0,
                "min_value": 0,
                "max_value": None,
                "unit": None,
                "description": "Number of recorded observations",
            }
        ]

    def _objects(self, objects: Any, manifest_id: str, topic: str) -> list[dict[str, Any]]:
        items = objects if isinstance(objects, list) else []
        normalized: list[dict[str, Any]] = []
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            object_id = self._slug(item.get("object_id") or item.get("name") or f"object-{index + 1}")
            normalized.append(
                {
                    "object_id": object_id,
                    "object_type": self._clean_text(item.get("object_type")) or "observation_item",
                    "name": self._clean_text(item.get("name")) or object_id.replace("-", " ").title(),
                    "properties": item.get("properties") if isinstance(item.get("properties"), dict) else {},
                    "metadata": item.get("metadata") if isinstance(item.get("metadata"), dict) else {},
                }
            )
        if normalized:
            return normalized
        return [
            {
                "object_id": f"{manifest_id}-object",
                "object_type": "observation_item",
                "name": topic,
                "properties": {},
                "metadata": {},
            }
        ]

    def _rules(self, rules: Any, manifest_id: str) -> list[dict[str, Any]]:
        items = rules if isinstance(rules, list) else []
        normalized: list[dict[str, Any]] = []
        for index, rule in enumerate(items):
            if not isinstance(rule, dict):
                continue
            rule_id = self._slug(rule.get("rule_id") or rule.get("name") or f"rule-{index + 1}")
            normalized.append(
                {
                    "rule_id": rule_id,
                    "name": self._clean_text(rule.get("name")) or rule_id.replace("-", " ").title(),
                    "trigger": self._clean_text(rule.get("trigger")) or "observation_added",
                    "condition": rule.get("condition") if isinstance(rule.get("condition"), dict) else {},
                    "action": rule.get("action") if isinstance(rule.get("action"), dict) else {"type": "record_observation"},
                    "enabled": bool(rule.get("enabled", True)),
                }
            )
        if normalized:
            return normalized
        return [
            {
                "rule_id": f"{manifest_id}-record-observation",
                "name": "Record Observation",
                "trigger": "observation_added",
                "condition": {},
                "action": {"type": "record_observation"},
                "enabled": True,
            }
        ]

    def _modes(self, modes: Any) -> list[str]:
        items = [str(mode).lower() for mode in modes] if isinstance(modes, list) else []
        filtered = [mode for mode in items if mode in self.VALID_MODES]
        return filtered or ["observation"]

    def _difficulty(self, difficulty: Any) -> str:
        value = str(difficulty or "easy").lower()
        return value if value in self.VALID_DIFFICULTIES else "easy"

    def _list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip().lower().replace(" ", "_") for item in value if str(item).strip()]

    def _clean_text(self, value: Any) -> str:
        return str(value).strip() if value is not None else ""

    def _slug(self, value: Any) -> str:
        text = str(value or "experiment").strip().lower()
        text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
        return text or "experiment"
