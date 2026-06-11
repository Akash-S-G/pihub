"""
Classroom Load Management Service

Handles:
- Multi-device coordination
- Transfer balancing
- Bandwidth-aware scheduling
- Queue prioritization
- Classroom load monitoring
"""

from __future__ import annotations

import time
from typing import Any


class ClassroomLoadManager:
    """Manage classroom device load and coordination"""

    def __init__(self, max_concurrent_transfers: int = 3) -> None:
        self.max_concurrent_transfers = max_concurrent_transfers
        self.active_transfers: dict[str, dict[str, Any]] = {}
        self.device_bandwidth: dict[str, float] = {}
        self.classroom_load_history: list[dict[str, Any]] = []

    def can_accept_transfer(self) -> bool:
        """Check if classroom can accept new transfer"""
        return len(self.active_transfers) < self.max_concurrent_transfers

    def register_transfer(
        self,
        transfer_id: str,
        device_id: str,
        pack_id: str,
        total_bytes: int,
    ) -> dict[str, Any]:
        """Register new active transfer"""
        if not self.can_accept_transfer():
            return {"status": "rejected", "reason": "classroom_at_capacity"}

        transfer = {
            "transfer_id": transfer_id,
            "device_id": device_id,
            "pack_id": pack_id,
            "total_bytes": total_bytes,
            "bytes_transferred": 0,
            "started_at": int(time.time()),
            "priority": 0,
        }
        self.active_transfers[transfer_id] = transfer
        return {"status": "ok", "transfer": transfer}

    def unregister_transfer(self, transfer_id: str) -> None:
        """Remove completed transfer from active set"""
        if transfer_id in self.active_transfers:
            del self.active_transfers[transfer_id]

    def update_transfer_priority(self, transfer_id: str, priority: int) -> bool:
        """Update transfer priority (higher = sooner)"""
        if transfer_id not in self.active_transfers:
            return False

        self.active_transfers[transfer_id]["priority"] = priority
        return True

    def get_queued_transfers(self) -> list[dict[str, Any]]:
        """Get active transfers sorted by priority"""
        return sorted(
            self.active_transfers.values(),
            key=lambda x: (-x["priority"], x["started_at"]),
        )

    def record_device_bandwidth(self, device_id: str, bandwidth_mbps: float) -> None:
        """Record device bandwidth measurement"""
        self.device_bandwidth[device_id] = bandwidth_mbps

    def get_device_bandwidth(self, device_id: str) -> float:
        """Get measured bandwidth for device"""
        return self.device_bandwidth.get(device_id, 5.0)  # Default 5 Mbps

    def estimate_transfer_time(self, transfer_id: str) -> int | None:
        """Estimate time remaining for transfer in seconds"""
        if transfer_id not in self.active_transfers:
            return None

        transfer = self.active_transfers[transfer_id]
        remaining_bytes = transfer["total_bytes"] - transfer["bytes_transferred"]
        bandwidth_mbps = self.get_device_bandwidth(transfer["device_id"])
        bandwidth_byteps = (bandwidth_mbps * 1024 * 1024) / 8

        if bandwidth_byteps > 0:
            return int(remaining_bytes / bandwidth_byteps)
        return None

    def get_classroom_load(self) -> dict[str, Any]:
        """Get classroom load metrics"""
        total_bandwidth = sum(self.device_bandwidth.values())
        total_bytes_in_flight = sum(t["total_bytes"] for t in self.active_transfers.values())

        return {
            "active_transfers": len(self.active_transfers),
            "max_concurrent": self.max_concurrent_transfers,
            "total_bandwidth_mbps": round(total_bandwidth, 2),
            "total_bytes_in_flight": total_bytes_in_flight,
            "avg_transfer_time_remaining": int(
                sum(self.estimate_transfer_time(tid) or 0 for tid in self.active_transfers) / max(1, len(self.active_transfers))
            ),
        }

    def record_load_snapshot(self) -> None:
        """Record snapshot of current classroom load"""
        snapshot = {
            "timestamp": int(time.time()),
            "active_transfers": len(self.active_transfers),
            "total_bandwidth": sum(self.device_bandwidth.values()),
        }
        self.classroom_load_history.append(snapshot)

        if len(self.classroom_load_history) > 1000:
            self.classroom_load_history = self.classroom_load_history[-1000:]

    def get_load_statistics(self) -> dict[str, Any]:
        """Get load statistics over time"""
        if not self.classroom_load_history:
            return {"status": "no_history"}

        active_counts = [s["active_transfers"] for s in self.classroom_load_history]
        avg_active = sum(active_counts) / len(active_counts)
        max_active = max(active_counts)

        return {
            "avg_active_transfers": round(avg_active, 2),
            "max_active_transfers": max_active,
            "history_size": len(self.classroom_load_history),
        }
