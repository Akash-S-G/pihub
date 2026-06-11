"""
Backend Recovery Coordination Service

Handles:
- Deferred sync recovery management
- Backend reconnect handling
- Scheduled retry coordination
- Metadata reconciliation
"""

from __future__ import annotations

import time
from typing import Any


class DeferredBackendSyncManager:
    """Manage deferred synchronization with backend"""

    def __init__(self) -> None:
        self.deferred_items: dict[str, dict[str, Any]] = {}
        self.sync_schedule: list[tuple[int, str]] = []

    def queue_deferred_sync(
        self,
        item_id: str,
        action: str,
        resource_type: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Queue item for deferred sync"""
        item = {
            "item_id": item_id,
            "action": action,
            "resource_type": resource_type,
            "payload": payload,
            "created_at": int(time.time()),
            "retry_count": 0,
            "status": "pending",
        }
        self.deferred_items[item_id] = item
        self.sync_schedule.append((item["created_at"], item_id))
        return item

    def get_pending_syncs(self) -> list[dict[str, Any]]:
        """Get all pending deferred syncs"""
        return [
            item
            for item in self.deferred_items.values()
            if item["status"] in ("pending", "retry")
        ]

    def mark_synced(self, item_id: str) -> bool:
        """Mark item as successfully synced"""
        if item_id not in self.deferred_items:
            return False
        self.deferred_items[item_id]["status"] = "complete"
        self.deferred_items[item_id]["synced_at"] = int(time.time())
        return True

    def mark_retry(self, item_id: str) -> bool:
        """Mark item for retry"""
        if item_id not in self.deferred_items:
            return False
        item = self.deferred_items[item_id]
        item["retry_count"] += 1
        if item["retry_count"] < 5:
            item["status"] = "retry"
            item["next_retry_at"] = int(time.time()) + (60 * (2 ** min(item["retry_count"], 4)))
            return True
        else:
            item["status"] = "failed"
            return False

    def get_deferred_status(self) -> dict[str, Any]:
        """Get deferred sync status"""
        pending = sum(1 for i in self.deferred_items.values() if i["status"] in ("pending", "retry"))
        complete = sum(1 for i in self.deferred_items.values() if i["status"] == "complete")
        failed = sum(1 for i in self.deferred_items.values() if i["status"] == "failed")

        return {
            "total_deferred": len(self.deferred_items),
            "pending": pending,
            "complete": complete,
            "failed": failed,
        }


class BackendRecoveryCoordinator:
    """Coordinate backend reconnection recovery"""

    def __init__(self, deferred_manager: DeferredBackendSyncManager) -> None:
        self.deferred = deferred_manager
        self.backend_available = True
        self.last_available_at = int(time.time())
        self.disconnection_count = 0
        self.recovery_history: list[dict[str, Any]] = []

    def on_backend_disconnect(self) -> None:
        """Handle backend becoming unavailable"""
        self.backend_available = False
        self.disconnection_count += 1
        self.recovery_history.append({
            "event": "disconnect",
            "at": int(time.time()),
            "disconnection_count": self.disconnection_count,
        })

    def on_backend_reconnect(self) -> None:
        """Handle backend becoming available"""
        self.backend_available = True
        self.last_available_at = int(time.time())
        self.recovery_history.append({
            "event": "reconnect",
            "at": int(time.time()),
            "deferred_items": len(self.deferred.get_pending_syncs()),
        })

    def get_backend_status(self) -> dict[str, Any]:
        """Get backend connectivity status"""
        return {
            "available": self.backend_available,
            "disconnection_count": self.disconnection_count,
            "last_available_at": self.last_available_at,
            "uptime_seconds": int(time.time()) - self.last_available_at if self.backend_available else 0,
        }


class PartialSyncRecoveryService:
    """Recover partial synchronization state"""

    def __init__(self) -> None:
        self.partial_syncs: dict[str, dict[str, Any]] = {}

    def record_partial_sync(
        self,
        sync_id: str,
        device_id: str,
        transferred_bytes: int,
        total_bytes: int,
        last_chunk_index: int,
    ) -> dict[str, Any]:
        """Record partial sync state"""
        record = {
            "sync_id": sync_id,
            "device_id": device_id,
            "transferred_bytes": transferred_bytes,
            "total_bytes": total_bytes,
            "last_chunk_index": last_chunk_index,
            "progress_percent": (transferred_bytes / total_bytes * 100) if total_bytes > 0 else 0,
            "recorded_at": int(time.time()),
        }
        self.partial_syncs[sync_id] = record
        return record

    def get_resumable_syncs(self) -> list[dict[str, Any]]:
        """Get syncs that can be resumed"""
        return [
            s
            for s in self.partial_syncs.values()
            if s.get("progress_percent", 0) > 0 and s.get("progress_percent", 0) < 100
        ]

    def mark_resumed(self, sync_id: str) -> bool:
        """Mark sync as resumed"""
        if sync_id in self.partial_syncs:
            self.partial_syncs[sync_id]["resumed_at"] = int(time.time())
            return True
        return False
