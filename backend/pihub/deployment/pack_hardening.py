"""
Educational Pack Hardening Service

Handles:
- Pack integrity validation
- Broadcast coordination
- Incremental distribution
- Transfer recovery coordination
"""

from __future__ import annotations

import hashlib
import time
from typing import Any


class PackValidator:
    """Validate educational pack integrity"""

    def __init__(self) -> None:
        self.validation_cache: dict[str, dict[str, Any]] = {}
        self.cache_ttl = 3600

    def compute_pack_checksum(self, file_path: str) -> str:
        """Compute SHA256 checksum of pack file"""
        try:
            sha256_hash = hashlib.sha256()
            with open(file_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except Exception:
            return ""

    def validate_pack(self, pack_id: str, file_path: str, expected_checksum: str) -> dict[str, Any]:
        """Validate pack integrity"""
        computed_checksum = self.compute_pack_checksum(file_path)
        is_valid = computed_checksum == expected_checksum

        result = {
            "pack_id": pack_id,
            "valid": is_valid,
            "computed_checksum": computed_checksum,
            "expected_checksum": expected_checksum,
            "validated_at": int(time.time()),
        }

        self.validation_cache[pack_id] = result
        return result

    def is_pack_valid(self, pack_id: str, file_path: str, expected_checksum: str) -> bool:
        """Quick pack validation check with caching"""
        cached = self.validation_cache.get(pack_id)
        if cached and int(time.time()) - cached.get("validated_at", 0) < self.cache_ttl:
            return cached["valid"]

        result = self.validate_pack(pack_id, file_path, expected_checksum)
        return result["valid"]


class BroadcastCoordinator:
    """Coordinate classroom-aware pack broadcasting"""

    def __init__(self) -> None:
        self.broadcast_history: dict[str, dict[str, Any]] = {}

    def create_broadcast(
        self,
        broadcast_id: str,
        pack_id: str,
        target_devices: list[str],
        subject_filter: str | None = None,
        grade_filter: int | None = None,
    ) -> dict[str, Any]:
        """Create new pack broadcast"""
        broadcast = {
            "broadcast_id": broadcast_id,
            "pack_id": pack_id,
            "target_devices": target_devices,
            "subject_filter": subject_filter,
            "grade_filter": grade_filter,
            "created_at": int(time.time()),
            "status": "pending",
            "completed_count": 0,
            "failed_count": 0,
        }
        self.broadcast_history[broadcast_id] = broadcast
        return broadcast

    def update_broadcast_status(
        self,
        broadcast_id: str,
        device_id: str,
        device_status: str,
    ) -> dict[str, Any] | None:
        """Update status for device in broadcast"""
        if broadcast_id not in self.broadcast_history:
            return None

        broadcast = self.broadcast_history[broadcast_id]
        if device_status == "complete":
            broadcast["completed_count"] += 1
        elif device_status == "failed":
            broadcast["failed_count"] += 1

        if broadcast["completed_count"] + broadcast["failed_count"] == len(broadcast["target_devices"]):
            broadcast["status"] = "complete"
            broadcast["completed_at"] = int(time.time())

        return broadcast

    def get_broadcast_status(self, broadcast_id: str) -> dict[str, Any] | None:
        """Get broadcast status"""
        return self.broadcast_history.get(broadcast_id)


class IncrementalDistributionManager:
    """Manage incremental pack updates"""

    def __init__(self) -> None:
        self.version_tracking: dict[str, dict[str, Any]] = {}

    def track_version(
        self,
        pack_id: str,
        version: str,
        size_bytes: int,
        checksum: str,
    ) -> dict[str, Any]:
        """Track pack version for incremental updates"""
        version_record = {
            "pack_id": pack_id,
            "version": version,
            "size_bytes": size_bytes,
            "checksum": checksum,
            "released_at": int(time.time()),
        }
        self.version_tracking[f"{pack_id}:{version}"] = version_record
        return version_record

    def get_version_history(self, pack_id: str) -> list[dict[str, Any]]:
        """Get version history for pack"""
        versions = [
            v
            for k, v in self.version_tracking.items()
            if k.startswith(f"{pack_id}:")
        ]
        return sorted(versions, key=lambda x: x["released_at"], reverse=True)

    def compute_incremental_delta(
        self,
        pack_id: str,
        current_version: str,
        target_version: str,
    ) -> dict[str, Any]:
        """Compute delta between versions for incremental update"""
        current_key = f"{pack_id}:{current_version}"
        target_key = f"{pack_id}:{target_version}"

        current_record = self.version_tracking.get(current_key)
        target_record = self.version_tracking.get(target_key)

        if not current_record or not target_record:
            return {"status": "error", "detail": "version_not_found"}

        return {
            "pack_id": pack_id,
            "from_version": current_version,
            "to_version": target_version,
            "current_size": current_record["size_bytes"],
            "target_size": target_record["size_bytes"],
            "size_delta": target_record["size_bytes"] - current_record["size_bytes"],
            "full_transfer_needed": current_record["checksum"] != target_record["checksum"],
        }
