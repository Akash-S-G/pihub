from __future__ import annotations

import os
import shutil
import time
from typing import Any


class HealthMonitor:
    """Monitor PiHub system health."""

    def __init__(self, store: Any) -> None:
        self.store = store
        self.start_time = time.time()

    def get_system_health(self) -> dict[str, Any]:
        """Get overall system health status."""
        devices = self.store.list_devices()
        sessions = self.store.list_sync_queue()
        cached = self.store.list_cached_packs()
        backend_state = self.store.get_backend_sync_state()

        online_devices = len([d for d in devices if d["status"] == "online"])
        offline_devices = len(devices) - online_devices

        uptime_seconds = int(time.time() - self.start_time)
        uptime_hours = uptime_seconds / 3600

        return {
            "status": "healthy" if online_devices > 0 else "idle",
            "uptime_hours": uptime_hours,
            "devices": {
                "total": len(devices),
                "online": online_devices,
                "offline": offline_devices,
            },
            "sync": {
                "pending": len([s for s in sessions if s.get("status") == "pending"]),
                "in_progress": len([s for s in sessions if s.get("status") == "transferring"]),
                "completed": len([s for s in sessions if s.get("status") == "complete"]),
            },
            "cache": {
                "total_packs": len(cached),
                "total_size_mb": sum(p.get("size_bytes", 0) for p in cached) / (1024 * 1024),
            },
            "backend": {
                "available": backend_state.get("backend_available", True),
                "offline_mode": backend_state.get("offline_mode", False),
                "pending_pushes": backend_state.get("pending_pushes", 0),
            },
        }

    def get_resource_usage(self) -> dict[str, Any]:
        """Get basic CPU, memory, disk, and uptime diagnostics."""
        cpu_percent = 0.0
        if hasattr(os, "getloadavg"):
            load_1, _, _ = os.getloadavg()
            cpu_percent = round(load_1 * 100, 2)

        memory_total_mb = 0.0
        memory_available_mb = 0.0
        try:
            with open("/proc/meminfo", "r", encoding="utf-8") as meminfo:
                data = meminfo.read().splitlines()
            values = {}
            for line in data:
                key, value = line.split(":", 1)
                values[key] = value.strip()
            memory_total_mb = float(values.get("MemTotal", "0 kB").split()[0]) / 1024
            memory_available_mb = float(values.get("MemAvailable", "0 kB").split()[0]) / 1024
        except Exception:
            pass

        disk_usage = shutil.disk_usage("/")
        uptime_seconds = int(time.time() - self.start_time)

        return {
            "cpu_percent": cpu_percent,
            "memory_total_mb": round(memory_total_mb, 2),
            "memory_available_mb": round(memory_available_mb, 2),
            "storage_total_gb": round(disk_usage.total / (1024 ** 3), 2),
            "storage_used_gb": round(disk_usage.used / (1024 ** 3), 2),
            "storage_free_gb": round(disk_usage.free / (1024 ** 3), 2),
            "uptime_seconds": uptime_seconds,
        }
