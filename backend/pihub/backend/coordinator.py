from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any

import httpx


class BackendCoordinator:
    """Coordinate with backend AI infrastructure."""

    def __init__(self, store: Any, backend_url: str) -> None:
        self.store = store
        self.backend_url = backend_url
        self.http = httpx.AsyncClient(timeout=30.0)
        self.sync_interval = 300
        self.last_sync = 0
        self.deferred_queue: list[dict[str, Any]] = []

    async def check_backend_health(self) -> bool:
        """Check if backend is available."""
        try:
            response = await self.http.get(f"{self.backend_url}/health")
            available = response.is_success
            self.store.set_backend_sync_state(available, not available)
            return available
        except Exception:
            self.store.set_backend_sync_state(False, True)
            return False

    async def sync_classroom_metadata(self) -> dict[str, Any]:
        """Sync classroom metadata with backend."""
        now = time.time()
        if now - self.last_sync < self.sync_interval:
            return {"status": "skipped", "reason": "sync_interval_not_elapsed"}

        try:
            available = await self.check_backend_health()
            if not available:
                return {"status": "backend_unavailable"}

            classroom = self.store.get_classroom()
            devices = self.store.list_devices()

            payload = {
                "classroom": classroom,
                "devices_count": len(devices),
                "devices_online": len([d for d in devices if d["status"] == "online"]),
                "timestamp": int(now),
            }
            response = await self.http.post(f"{self.backend_url}/classroom", json=payload)
            if response.is_success:
                self.last_sync = now
                return {"status": "ok", "synced_at": int(now)}
            return {"status": "sync_failed", "code": response.status_code}
        except Exception as e:
            return {"status": "error", "detail": str(e)}

    async def pull_assignments(self, classroom: str | None = None) -> list[dict[str, Any]]:
        """Pull assignments from backend."""
        try:
            available = await self.check_backend_health()
            if not available:
                return []
            payload = {"classroom": classroom}
            response = await self.http.post(f"{self.backend_url}/assignments", json=payload)
            if response.is_success:
                return response.json().get("assignments", [])
        except Exception:
            pass
        return []

    async def push_progress(self, device_id: str, progress_data: dict[str, Any]) -> bool:
        """Push student progress to backend."""
        try:
            available = await self.check_backend_health()
            if not available:
                self.queue_deferred_sync("push_progress", "student_progress", device_id, progress_data)
                return False
            payload = {"device_id": device_id, **progress_data}
            response = await self.http.post(f"{self.backend_url}/progress", json=payload)
            return response.is_success
        except Exception:
            return False

    def queue_deferred_sync(self, action: str, resource_type: str, resource_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Queue sync work locally when backend is unavailable."""
        item = {
            "item_id": str(uuid.uuid4()),
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "payload": payload,
            "created_at": int(time.time()),
            "status": "pending",
        }
        self.deferred_queue.append(item)
        self.store.set_backend_sync_state(False, True, len(self.deferred_queue))
        return item

    async def process_deferred_syncs(self) -> dict[str, Any]:
        """Retry deferred sync operations when backend is reachable."""
        available = await self.check_backend_health()
        if not available:
            return {"status": "backend_unavailable", "pending": len(self.deferred_queue)}

        synced = 0
        failed = 0
        remaining: list[dict[str, Any]] = []

        for item in self.deferred_queue:
            try:
                response = await self.http.post(
                    f"{self.backend_url}/{item['resource_type']}",
                    json=item["payload"],
                )
                if response.is_success:
                    synced += 1
                else:
                    failed += 1
                    item["status"] = "failed"
                    remaining.append(item)
            except Exception:
                failed += 1
                item["status"] = "failed"
                remaining.append(item)

        self.deferred_queue = remaining
        self.store.set_backend_sync_state(True, False, len(self.deferred_queue))
        return {"status": "ok", "synced": synced, "failed": failed, "remaining": len(self.deferred_queue)}

    def get_backend_status(self) -> dict[str, Any]:
        """Return backend availability and deferred sync health."""
        state = self.store.get_backend_sync_state()
        return {
            "backend_available": state.get("backend_available", True),
            "offline_mode": state.get("offline_mode", False),
            "pending_pushes": state.get("pending_pushes", 0),
            "last_sync_time": state.get("last_sync_time"),
            "last_check_time": state.get("last_check_time"),
            "deferred_queue": len(self.deferred_queue),
        }

    def queue_snapshot(self) -> list[dict[str, Any]]:
        """Get a copy of the deferred queue for diagnostics."""
        return [json.loads(json.dumps(item)) for item in self.deferred_queue]

    async def close(self) -> None:
        """Close HTTP client."""
        await self.http.aclose()
