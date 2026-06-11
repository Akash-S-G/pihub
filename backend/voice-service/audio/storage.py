from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class AudioObject:
    asset_id: str
    content: bytes
    content_type: str = "audio/wav"
    checksum: str | None = None


class AudioStorage(ABC):
    @abstractmethod
    async def get(self, asset_id: str) -> AudioObject | None:
        """Get audio bytes from filesystem, MinIO, or S3."""

    @abstractmethod
    async def put(self, asset_id: str, content: bytes, content_type: str) -> AudioObject:
        """Persist audio bytes to filesystem, MinIO, or S3."""


class FileSystemAudioStorage(AudioStorage):
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    async def get(self, asset_id: str) -> AudioObject | None:
        path = self._path(asset_id)
        if not path.exists() or not path.is_file():
            return None
        content = path.read_bytes()
        return AudioObject(asset_id=asset_id, content=content, checksum=hashlib.sha256(content).hexdigest())

    async def put(self, asset_id: str, content: bytes, content_type: str = "audio/wav") -> AudioObject:
        path = self._path(asset_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return AudioObject(asset_id=asset_id, content=content, content_type=content_type, checksum=hashlib.sha256(content).hexdigest())

    def _path(self, asset_id: str) -> Path:
        safe = asset_id.replace("/", "_").replace("..", "_")
        suffix = "" if "." in safe else ".wav"
        return self.root / f"{safe}{suffix}"
