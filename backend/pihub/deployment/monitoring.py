"""
Distributed Monitoring Service

Handles:
- Classroom metrics collection
- Synchronization metrics
- Network diagnostics
- Infrastructure health tracking
"""

from __future__ import annotations

import time
from typing import Any


class ClassroomMetricsCollector:
    """Collect classroom-level metrics"""

    def __init__(self) -> None:
        self.metrics_history: list[dict[str, Any]] = []
        self.device_activity: dict[str, dict[str, Any]] = {}

    def record_device_activity(
        self,
        device_id: str,
        activity_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record device activity"""
        self.device_activity[device_id] = {
            "device_id": device_id,
            "last_activity": int(time.time()),
            "last_activity_type": activity_type,
            "metadata": metadata or {},
        }

    def collect_classroom_metrics(
        self,
        active_devices: int,
        total_devices: int,
        pending_syncs: int,
        cached_packs: int,
    ) -> dict[str, Any]:
        """Collect classroom metrics snapshot"""
        metrics = {
            "timestamp": int(time.time()),
            "active_devices": active_devices,
            "total_devices": total_devices,
            "device_online_percent": (active_devices / total_devices * 100) if total_devices > 0 else 0,
            "pending_syncs": pending_syncs,
            "cached_packs": cached_packs,
            "device_activity_count": len(self.device_activity),
        }
        self.metrics_history.append(metrics)

        if len(self.metrics_history) > 1000:
            self.metrics_history = self.metrics_history[-1000:]

        return metrics

    def get_classroom_summary(self) -> dict[str, Any]:
        """Get classroom metrics summary"""
        if not self.metrics_history:
            return {"status": "no_data"}

        recent = self.metrics_history[-1]
        oldest = self.metrics_history[0]

        avg_online_percent = sum(m["device_online_percent"] for m in self.metrics_history) / len(self.metrics_history)

        return {
            "current": recent,
            "average_online_percent": round(avg_online_percent, 2),
            "metrics_samples": len(self.metrics_history),
            "collection_period_hours": (recent["timestamp"] - oldest["timestamp"]) / 3600,
        }


class SyncMetricsService:
    """Track synchronization metrics"""

    def __init__(self) -> None:
        self.sync_events: list[dict[str, Any]] = []
        self.transfer_stats: dict[str, dict[str, Any]] = {}

    def record_sync_event(
        self,
        event_type: str,
        device_id: str,
        pack_id: str,
        status: str,
        duration_seconds: int | None = None,
        bytes_transferred: int | None = None,
    ) -> None:
        """Record sync event"""
        event = {
            "event_type": event_type,
            "device_id": device_id,
            "pack_id": pack_id,
            "status": status,
            "duration_seconds": duration_seconds,
            "bytes_transferred": bytes_transferred,
            "timestamp": int(time.time()),
        }
        self.sync_events.append(event)

        if len(self.sync_events) > 1000:
            self.sync_events = self.sync_events[-1000:]

    def record_transfer_stats(
        self,
        pack_id: str,
        total_transfers: int,
        successful: int,
        failed: int,
        avg_duration_seconds: float,
    ) -> None:
        """Record transfer statistics"""
        self.transfer_stats[pack_id] = {
            "pack_id": pack_id,
            "total_transfers": total_transfers,
            "successful": successful,
            "failed": failed,
            "success_rate": (successful / total_transfers * 100) if total_transfers > 0 else 0,
            "avg_duration_seconds": avg_duration_seconds,
            "updated_at": int(time.time()),
        }

    def get_sync_metrics(self, hours: int = 24) -> dict[str, Any]:
        """Get sync metrics for time period"""
        cutoff_time = int(time.time()) - (hours * 3600)
        recent_events = [e for e in self.sync_events if e["timestamp"] >= cutoff_time]

        successful = sum(1 for e in recent_events if e["status"] == "complete")
        failed = sum(1 for e in recent_events if e["status"] == "failed")
        total = len(recent_events)

        avg_duration = (
            sum(e["duration_seconds"] or 0 for e in recent_events if e["duration_seconds"]) / successful
            if successful > 0
            else 0
        )

        return {
            "period_hours": hours,
            "total_sync_events": total,
            "successful": successful,
            "failed": failed,
            "success_rate": (successful / total * 100) if total > 0 else 0,
            "avg_sync_duration_seconds": round(avg_duration, 2),
        }


class NetworkDiagnosticsManager:
    """Track network performance and diagnostics"""

    def __init__(self) -> None:
        self.network_events: list[dict[str, Any]] = []
        self.device_connectivity: dict[str, dict[str, Any]] = {}

    def record_connectivity_event(
        self,
        device_id: str,
        event_type: str,
        signal_strength: int | None = None,
        latency_ms: int | None = None,
    ) -> None:
        """Record device connectivity event"""
        event = {
            "device_id": device_id,
            "event_type": event_type,
            "signal_strength": signal_strength,
            "latency_ms": latency_ms,
            "timestamp": int(time.time()),
        }
        self.network_events.append(event)

        self.device_connectivity[device_id] = {
            "device_id": device_id,
            "last_event": event_type,
            "last_signal_strength": signal_strength,
            "last_latency_ms": latency_ms,
            "last_update": int(time.time()),
        }

        if len(self.network_events) > 1000:
            self.network_events = self.network_events[-1000:]

    def get_network_health(self) -> dict[str, Any]:
        """Get network health summary"""
        if not self.device_connectivity:
            return {"status": "no_data"}

        latencies = [
            d["last_latency_ms"]
            for d in self.device_connectivity.values()
            if d["last_latency_ms"] is not None
        ]
        signals = [
            d["last_signal_strength"]
            for d in self.device_connectivity.values()
            if d["last_signal_strength"] is not None
        ]

        return {
            "connected_devices": len(self.device_connectivity),
            "avg_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else 0,
            "min_latency_ms": min(latencies) if latencies else 0,
            "max_latency_ms": max(latencies) if latencies else 0,
            "avg_signal_strength": round(sum(signals) / len(signals), 2) if signals else 0,
        }
