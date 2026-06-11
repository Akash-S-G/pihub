from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class PackMetadataStore:
    def __init__(self, index_path: Path) -> None:
        self.index_path = index_path
        self.index_path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> list[dict[str, Any]]:
        if not self.index_path.exists():
            return []
        return json.loads(self.index_path.read_text(encoding="utf-8"))

    def _write(self, records: list[dict[str, Any]]) -> None:
        temp_path = self.index_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(records, indent=2, sort_keys=True), encoding="utf-8")
        temp_path.replace(self.index_path)

    def list(self) -> list[dict[str, Any]]:
        return self._read()

    def get(self, pack_id: str, version: str | None = None) -> dict[str, Any] | None:
        for record in self._read():
            if record.get("pack_id") != pack_id:
                continue
            if version is not None and record.get("version") != version:
                continue
            return record
        return None

    def upsert(self, record: dict[str, Any]) -> dict[str, Any]:
        records = [existing for existing in self._read() if not (existing.get("pack_id") == record.get("pack_id") and existing.get("version") == record.get("version"))]
        records.append(record)
        self._write(records)
        return record

    def remove(self, pack_id: str, version: str | None = None) -> None:
        records = []
        for record in self._read():
            if record.get("pack_id") != pack_id:
                records.append(record)
                continue
            if version is not None and record.get("version") != version:
                records.append(record)
        self._write(records)
