from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from schemas.experiment_registry_models import ExperimentDefinition


def _model_validate(model_type: type[ExperimentDefinition], payload: dict[str, Any]) -> ExperimentDefinition:
    if hasattr(model_type, "model_validate"):
        return model_type.model_validate(payload)
    return model_type.parse_obj(payload)


def _model_dump(model: ExperimentDefinition) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return json.loads(model.json())


class JsonExperimentManifestRepository:
    def __init__(self, storage_path: Path | str | None = None) -> None:
        self.storage_path = Path(storage_path or Path(__file__).resolve().parents[1] / "storage" / "seed_experiments.json")

    def _load_records(self) -> list[dict[str, Any]]:
        if not self.storage_path.exists():
            return []
        data = json.loads(self.storage_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            records = data.get("experiments", [])
            return records if isinstance(records, list) else []
        return data if isinstance(data, list) else []

    def list_experiments(self) -> list[ExperimentDefinition]:
        return [_model_validate(ExperimentDefinition, record) for record in self._load_records()]

    def get_experiment(self, experiment_id: str) -> ExperimentDefinition | None:
        for experiment in self.list_experiments():
            if experiment.manifest.id == experiment_id:
                return experiment
        return None

    def save_experiment(self, experiment: ExperimentDefinition) -> ExperimentDefinition:
        records = self.list_experiments()
        by_id = {record.manifest.id: record for record in records}
        by_id[experiment.manifest.id] = experiment
        payload = {"experiments": [_model_dump(record) for record in by_id.values()]}
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return experiment

    def delete_experiment(self, experiment_id: str) -> bool:
        records = self.list_experiments()
        remaining = [record for record in records if record.manifest.id != experiment_id]
        if len(remaining) == len(records):
            return False
        payload = {"experiments": [_model_dump(record) for record in remaining]}
        self.storage_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return True
