from __future__ import annotations

import json
from pathlib import Path

from models import AudioManifest


class AudioManifestRegistry:
    """Resolve pre-generated chapter audio assets before AI generation."""

    def __init__(self, manifest_path: str | Path | None = None) -> None:
        self.manifest_path = Path(manifest_path) if manifest_path else None
        self._manifests: dict[str, AudioManifest] = {}
        if self.manifest_path and self.manifest_path.exists():
            self.load(self.manifest_path)

    def load(self, path: str | Path) -> None:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        records = data if isinstance(data, list) else data.get("chapters", [])
        for item in records:
            manifest = _model_validate(AudioManifest, item)
            self._manifests[manifest.chapter_id] = manifest

    def get(self, chapter_id: str | None) -> AudioManifest | None:
        if not chapter_id:
            return None
        return self._manifests.get(chapter_id)

    def resolve(self, chapter_id: str | None, topic: str | None = None, kind: str | None = None) -> str | None:
        manifest = self.get(chapter_id)
        if not manifest:
            return None
        if kind == "summary" and manifest.summary:
            return manifest.summary
        if kind == "glossary" and manifest.glossary:
            return manifest.glossary
        if topic:
            normalized = topic.lower()
            for asset_id in manifest.concepts:
                if normalized in asset_id.lower():
                    return asset_id
        return None


def _model_validate(model_cls, data):
    if hasattr(model_cls, "model_validate"):
        return model_cls.model_validate(data)
    return model_cls.parse_obj(data)
