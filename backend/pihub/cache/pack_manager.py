from __future__ import annotations

import os
from pathlib import Path
from typing import Any


class PackManager:
    """Educational pack caching and distribution manager."""

    def __init__(self, store: Any, cache_dir: Path, max_cache_size_mb: int = 500) -> None:
        self.store = store
        self.cache_dir = cache_dir
        self.max_cache_size_bytes = max_cache_size_mb * 1024 * 1024
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def cache_pack(self, pack_id: str, pack_name: str, version: str, file_path: str, checksum: str, size_bytes: int, subject: str | None = None, grade: int | None = None, chapter: str | None = None) -> None:
        """Add a pack to the local cache."""
        self.store.cache_pack(pack_id, pack_name, version, file_path, checksum, size_bytes, subject, grade, chapter, {"cached": True})

    def is_pack_cached(self, pack_id: str) -> bool:
        """Check if a pack is in the local cache."""
        return self.store.get_cached_pack(pack_id) is not None

    def get_cached_pack(self, pack_id: str) -> dict[str, Any] | None:
        """Get cached pack metadata."""
        pack = self.store.get_cached_pack(pack_id)
        if pack:
            self.store.touch_cached_pack(pack_id)
        return pack

    def list_cached_packs(self) -> list[dict[str, Any]]:
        """List all cached packs."""
        return self.store.list_cached_packs()

    def evict_if_needed(self) -> None:
        """Evict least-used packs if cache exceeds max size."""
        cached = self.store.list_cached_packs()
        total_size = sum(p.get("size_bytes", 0) for p in cached)

        if total_size > self.max_cache_size_bytes:
            for pack in reversed(cached):
                if total_size <= self.max_cache_size_bytes:
                    break
                file_path = Path(pack.get("file_path"))
                if file_path.exists():
                    file_path.unlink()
                total_size -= pack.get("size_bytes", 0)

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        cached = self.store.list_cached_packs()
        total_size = sum(p.get("size_bytes", 0) for p in cached)
        total_accesses = sum(p.get("access_count", 0) for p in cached)

        return {
            "total_packs": len(cached),
            "total_size_mb": total_size / (1024 * 1024),
            "max_size_mb": self.max_cache_size_bytes / (1024 * 1024),
            "total_accesses": total_accesses,
            "packs": cached,
        }
