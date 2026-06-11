from __future__ import annotations

import re
from typing import Protocol

from app.ai.models import ExperimentGenerationRequest, ExperimentRefineRequest


class ExperimentManifestProvider(Protocol):
    provider_name: str

    def generate(self, request: ExperimentGenerationRequest, prompt: str) -> dict:
        ...

    def refine(self, request: ExperimentRefineRequest, prompt: str) -> dict:
        ...


class LocalManifestDraftProvider:
    provider_name = "local_manifest_draft"

    SUBJECT_KEYWORDS = {
        "Physics": ("motion", "force", "pendulum", "light", "lens", "electric", "voltage", "current", "sound"),
        "Chemistry": ("acid", "base", "reaction", "salt", "solution", "ph", "mixture"),
        "Biology": ("plant", "growth", "leaf", "cell", "seed", "germination", "organism"),
        "Mathematics": ("angle", "graph", "ratio", "triangle", "probability", "algebra"),
        "Environmental Science": ("water", "soil", "weather", "pollution", "ecosystem", "climate"),
    }

    SENSOR_KEYWORDS = {
        "gps": "gps",
        "accelerometer": "accelerometer",
        "gyroscope": "gyroscope",
        "camera": "camera",
        "microphone": "microphone",
        "barometer": "barometer",
        "light": "light",
    }

    def generate(self, request: ExperimentGenerationRequest, prompt: str) -> dict:
        text = request.description
        subject = request.subject or self._infer_subject(text)
        topic = request.topic or self._infer_topic(text)
        title = self._title(text, topic)
        variables = self._variables(text)
        required_sensors = request.required_sensors or self._sensors(text)
        supported_modes = request.supported_modes or self._modes(text, required_sensors)
        return {
            "title": title,
            "description": text,
            "subject": subject,
            "topic": topic,
            "difficulty": request.difficulty or "easy",
            "supported_modes": supported_modes,
            "required_sensors": required_sensors,
            "variables": variables,
            "objects": [
                {
                    "object_id": "experiment-object",
                    "object_type": "observation_item",
                    "name": topic,
                    "properties": {},
                    "metadata": {},
                }
            ],
            "rules": [],
            "scene": {},
            "metadata": {"prompt": prompt},
        }

    def refine(self, request: ExperimentRefineRequest, prompt: str) -> dict:
        manifest = dict(request.manifest)
        instructions = request.instructions.lower()

        sensors = list(manifest.get("required_sensors", [])) if isinstance(manifest.get("required_sensors"), list) else []
        modes = list(manifest.get("supported_modes", [])) if isinstance(manifest.get("supported_modes"), list) else []
        variables = list(manifest.get("variables", [])) if isinstance(manifest.get("variables"), list) else []

        for keyword, sensor in self.SENSOR_KEYWORDS.items():
            if keyword in instructions and sensor not in sensors:
                sensors.append(sensor)
        for mode in ("sensor", "simulation", "hybrid", "observation"):
            if mode in instructions and mode not in modes:
                modes.append(mode)
        if "fallback" in instructions and "simulation" not in modes:
            modes.append("simulation")

        variable_match = re.search(r"add\s+([a-zA-Z_ -]+?)\s+variable", instructions)
        if variable_match:
            name = variable_match.group(1).strip().replace(" ", "_")
            variables.append(
                {
                    "name": name,
                    "type": "number",
                    "default_value": None,
                    "min_value": None,
                    "max_value": None,
                    "unit": None,
                    "description": f"Configurable variable: {name}",
                }
            )

        manifest["required_sensors"] = sensors
        manifest["supported_modes"] = modes
        manifest["variables"] = variables
        manifest.setdefault("metadata", {})["last_refinement_prompt"] = prompt
        return manifest

    def _infer_subject(self, text: str) -> str:
        lowered = text.lower()
        for subject, keywords in self.SUBJECT_KEYWORDS.items():
            if any(keyword in lowered for keyword in keywords):
                return subject
        return "General Science"

    def _infer_topic(self, text: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9 ]+", " ", text).strip()
        words = [word for word in cleaned.split() if len(word) > 2]
        if not words:
            return "Experiment"
        stopwords = {"create", "make", "design", "experiment", "observe", "study", "about", "with", "using", "for"}
        topic_words = [word for word in words if word.lower() not in stopwords][:4]
        return " ".join(topic_words or words[:3]).title()

    def _title(self, text: str, topic: str) -> str:
        lowered = text.lower()
        if "experiment" in lowered:
            return topic if topic.lower().endswith("experiment") else f"{topic} Experiment"
        return f"{topic} Experiment"

    def _variables(self, text: str) -> list[dict]:
        lowered = text.lower()
        variables: list[dict] = []
        for name in ("time", "distance", "temperature", "mass", "length", "voltage", "current", "velocity"):
            if name in lowered:
                variables.append(
                    {
                        "name": name,
                        "type": "number",
                        "default_value": None,
                        "min_value": None,
                        "max_value": None,
                        "unit": None,
                        "description": f"Configurable variable: {name}",
                    }
                )
        return variables

    def _sensors(self, text: str) -> list[str]:
        lowered = text.lower()
        return [sensor for keyword, sensor in self.SENSOR_KEYWORDS.items() if keyword in lowered]

    def _modes(self, text: str, sensors: list[str]) -> list[str]:
        lowered = text.lower()
        modes: list[str] = []
        if sensors:
            modes.append("sensor")
        if "simulation" in lowered or "fallback" in lowered:
            modes.append("simulation")
        if "hybrid" in lowered:
            modes.append("hybrid")
        if "observation" in lowered or not modes:
            modes.append("observation")
        return modes
