from __future__ import annotations

from pathlib import Path

from .storage_layout import StorageLayout


class PackLocator:
    def __init__(self, storage_root: Path) -> None:
        self.storage_root = storage_root

    def pack_dir(self, pack_id: str, grade: int | None = None, subject: str | None = None, chapter: str | None = None) -> Path:
        normalized = StorageLayout.pack_directory_name(grade, subject, chapter, pack_id)
        return self.storage_root / normalized

    def manifest_path(self, pack_dir: Path) -> Path:
        return pack_dir / "manifest.json"

    def archive_path(self, pack_dir: Path) -> Path:
        return pack_dir.with_suffix(".tar.gz")

    def pack_exists(self, pack_dir: Path) -> bool:
        return self.manifest_path(pack_dir).exists()
