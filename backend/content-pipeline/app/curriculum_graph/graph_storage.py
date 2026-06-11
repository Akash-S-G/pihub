from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class GraphStorage:
    """Persist curriculum relations separately from chunk payloads."""

    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict[str, Any]:
        if not self.file_path.exists():
            return {"topic_relations": {}, "prerequisites": {}, "concept_links": {}}
        return json.loads(self.file_path.read_text(encoding="utf-8"))

    def save(self, graph_data: dict[str, Any]) -> None:
        self.file_path.write_text(json.dumps(graph_data, indent=2, ensure_ascii=False), encoding="utf-8")
