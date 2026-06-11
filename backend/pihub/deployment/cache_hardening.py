"""
Distributed Cache Hardening Service

Handles:
- Cache integrity validation
- Automatic cleanup
- Storage diagnostics
- Corrupted cache recovery
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any


class CacheValidator:
    """Validate cache integrity"""

    def __init__(self) -> None:
        self.validation_results: dict[str, dict[str, Any]] = {}

    def validate_cache_file(self, file_path: str, expected_checksum: str) -> dict[str, Any]:
        """Validate cache file integrity"""
        try:
            path = Path(file_path)
            if not path.exists():
                return {"file": file_path, "valid": False, "error": "file_not_found"}

            sha256_hash = hashlib.sha256()
            with open(file_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)

            computed_checksum = sha256_hash.hexdigest()
            is_valid = computed_checksum == expected_checksum

            result = {
                "file": file_path,
                "valid": is_valid,
                "computed_checksum": computed_checksum,
                "expected_checksum": expected_checksum,
                "file_size": path.stat().st_size,
                "validated_at": int(time.time()),
            }
            self.validation_results[file_path] = result
            return result
        except Exception as e:
            return {"file": file_path, "valid": False, "error": str(e)}

    def get_invalid_entries(self) -> list[str]:
        """Get list of invalid cache entries"""
        return [k for k, v in self.validation_results.items() if not v["valid"]]


class CacheCleanupService:
    """Manage automatic cache cleanup"""

    def __init__(self, cache_dir: Path | None = None) -> None:
        self.cache_dir = cache_dir or Path("/cache")
        self.cleanup_history: list[dict[str, Any]] = []

    def cleanup_stale_entries(self, days_old: int = 30) -> dict[str, Any]:
        """Remove stale cache entries"""
        if not self.cache_dir.exists():
            return {"status": "cache_dir_not_found", "removed": 0}

        cutoff_time = int(time.time()) - (days_old * 86400)
        removed_count = 0
        total_freed_bytes = 0

        try:
            for file_path in self.cache_dir.glob("**/*"):
                if file_path.is_file():
                    mtime = file_path.stat().st_mtime
                    if mtime < cutoff_time:
                        file_size = file_path.stat().st_size
                        file_path.unlink()
                        removed_count += 1
                        total_freed_bytes += file_size

            record = {
                "cleanup_at": int(time.time()),
                "removed_count": removed_count,
                "freed_bytes": total_freed_bytes,
                "freed_mb": round(total_freed_bytes / (1024 * 1024), 2),
            }
            self.cleanup_history.append(record)

            return {"status": "ok", **record}
        except Exception as e:
            return {"status": "error", "detail": str(e)}

    def remove_corrupted_entries(self, corrupted_files: list[str]) -> dict[str, Any]:
        """Remove corrupted cache files"""
        removed_count = 0
        total_freed_bytes = 0

        for file_path_str in corrupted_files:
            try:
                file_path = Path(file_path_str)
                if file_path.exists():
                    file_size = file_path.stat().st_size
                    file_path.unlink()
                    removed_count += 1
                    total_freed_bytes += file_size
            except Exception:
                pass

        return {
            "status": "ok",
            "removed": removed_count,
            "freed_bytes": total_freed_bytes,
            "freed_mb": round(total_freed_bytes / (1024 * 1024), 2),
        }


class StorageDiagnosticsManager:
    """Monitor storage health and usage"""

    def __init__(self, cache_dir: Path | None = None) -> None:
        self.cache_dir = cache_dir or Path("/cache")
        self.usage_history: list[dict[str, Any]] = []

    def get_cache_usage(self) -> dict[str, Any]:
        """Get cache storage usage"""
        if not self.cache_dir.exists():
            return {"status": "cache_dir_not_found"}

        total_size = 0
        file_count = 0

        try:
            for file_path in self.cache_dir.glob("**/*"):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
                    file_count += 1

            return {
                "total_bytes": total_size,
                "total_mb": round(total_size / (1024 * 1024), 2),
                "total_gb": round(total_size / (1024 * 1024 * 1024), 2),
                "file_count": file_count,
            }
        except Exception as e:
            return {"status": "error", "detail": str(e)}

    def record_usage_snapshot(self) -> None:
        """Record cache usage snapshot for trending"""
        usage = self.get_cache_usage()
        if usage.get("status") != "error":
            snapshot = {
                "timestamp": int(time.time()),
                "total_mb": usage.get("total_mb"),
                "file_count": usage.get("file_count"),
            }
            self.usage_history.append(snapshot)

            if len(self.usage_history) > 100:
                self.usage_history = self.usage_history[-100:]

    def get_storage_trend(self) -> dict[str, Any]:
        """Get storage usage trend"""
        if not self.usage_history or len(self.usage_history) < 2:
            return {"status": "insufficient_data"}

        recent = self.usage_history[-1]
        oldest = self.usage_history[0]
        growth_mb = recent["total_mb"] - oldest["total_mb"]
        time_delta_hours = (recent["timestamp"] - oldest["timestamp"]) / 3600

        return {
            "current_usage_mb": recent["total_mb"],
            "growth_mb": round(growth_mb, 2),
            "growth_rate_mb_per_hour": round(growth_mb / max(1, time_delta_hours), 2),
            "samples": len(self.usage_history),
        }
