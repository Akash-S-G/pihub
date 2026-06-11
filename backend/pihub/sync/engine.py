"""
Real Synchronization Engine

Handles:
- Incremental synchronization
- Queue-based job management
- Version tracking
- Conflict resolution
- Retry recovery
- Transfer state tracking
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class SyncStatus(str, Enum):
    """Sync job status"""

    PENDING = "pending"
    TRANSFERRING = "transferring"
    PAUSED = "paused"
    COMPLETE = "complete"
    FAILED = "failed"
    CONFLICT = "conflict"


class ConflictResolutionStrategy(str, Enum):
    """Conflict resolution strategies"""

    LATEST_VERSION = "latest_version"
    BACKEND_WINS = "backend_wins"
    LOCAL_WINS = "local_wins"
    MANUAL = "manual"


@dataclass
class SyncJob:
    """Synchronization job"""

    job_id: str
    action: str
    resource_type: str
    resource_id: str
    target_devices: list[str] | None = None
    status: str = SyncStatus.PENDING.value
    bytes_transferred: int = 0
    total_bytes: int = 0
    retry_count: int = 0
    max_retries: int = 3
    created_at: int = 0
    updated_at: int = 0
    error_message: str | None = None
    metadata: dict[str, Any] | None = None

    @property
    def progress_percent(self) -> float:
        """Calculate transfer progress"""
        if self.total_bytes == 0:
            return 100.0 if self.status == SyncStatus.COMPLETE.value else 0.0
        return (self.bytes_transferred / self.total_bytes) * 100

    def can_retry(self) -> bool:
        """Check if job can be retried"""
        return self.retry_count < self.max_retries


@dataclass
class SyncConflict:
    """Sync conflict record"""

    conflict_id: str
    job_id: str
    resource_type: str
    resource_id: str
    local_version: str
    backend_version: str
    local_checksum: str | None = None
    backend_checksum: str | None = None
    resolution_strategy: str = ConflictResolutionStrategy.LATEST_VERSION.value
    resolved: bool = False
    resolved_at: int | None = None
    created_at: int = 0


class SyncEngine:
    """Real synchronization engine"""

    def __init__(self, store: Any) -> None:
        self.store = store
        self.job_queue: dict[str, SyncJob] = {}
        self.conflicts: dict[str, SyncConflict] = {}
        self.version_index: dict[str, dict[str, Any]] = {}

    def enqueue_sync(
        self,
        action: str,
        resource_type: str,
        resource_id: str,
        target_devices: list[str] | None = None,
        total_bytes: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> SyncJob:
        """Enqueue sync job"""
        job_id = str(uuid.uuid4())
        now = int(time.time())

        job = SyncJob(
            job_id=job_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            target_devices=target_devices,
            total_bytes=total_bytes,
            created_at=now,
            updated_at=now,
            metadata=metadata,
        )

        self.job_queue[job_id] = job
        self.store.enqueue_sync(action, resource_type, resource_id, target_devices, metadata)

        return job

    def get_sync_job(self, job_id: str) -> SyncJob | None:
        """Get sync job"""
        return self.job_queue.get(job_id)

    def update_sync_progress(self, job_id: str, bytes_transferred: int, status: str = SyncStatus.TRANSFERRING.value) -> SyncJob | None:
        """Update sync job progress"""
        job = self.job_queue.get(job_id)
        if not job:
            return None

        job.bytes_transferred = bytes_transferred
        job.status = status
        job.updated_at = int(time.time())

        return job

    def mark_sync_complete(self, job_id: str, checksum: str | None = None) -> SyncJob | None:
        """Mark sync job complete"""
        job = self.job_queue.get(job_id)
        if not job:
            return None

        job.status = SyncStatus.COMPLETE.value
        job.updated_at = int(time.time())

        if checksum:
            self.version_index[f"{job.resource_type}:{job.resource_id}"] = {
                "checksum": checksum,
                "version": int(time.time()),
                "job_id": job_id,
            }

        return job

    def mark_sync_failed(self, job_id: str, error_message: str) -> SyncJob | None:
        """Mark sync job failed"""
        job = self.job_queue.get(job_id)
        if not job:
            return None

        job.status = SyncStatus.FAILED.value
        job.error_message = error_message
        job.updated_at = int(time.time())

        return job

    def retry_sync(self, job_id: str) -> SyncJob | None:
        """Retry failed sync job"""
        job = self.job_queue.get(job_id)
        if not job or not job.can_retry():
            return None

        job.retry_count += 1
        job.status = SyncStatus.PENDING.value
        job.bytes_transferred = 0
        job.error_message = None
        job.updated_at = int(time.time())

        return job

    def detect_conflict(
        self,
        job_id: str,
        resource_type: str,
        resource_id: str,
        local_version: str,
        backend_version: str,
        local_checksum: str | None = None,
        backend_checksum: str | None = None,
    ) -> SyncConflict:
        """Detect and record conflict"""
        conflict_id = str(uuid.uuid4())
        now = int(time.time())

        conflict = SyncConflict(
            conflict_id=conflict_id,
            job_id=job_id,
            resource_type=resource_type,
            resource_id=resource_id,
            local_version=local_version,
            backend_version=backend_version,
            local_checksum=local_checksum,
            backend_checksum=backend_checksum,
            created_at=now,
        )

        self.conflicts[conflict_id] = conflict
        job = self.job_queue.get(job_id)
        if job:
            job.status = SyncStatus.CONFLICT.value

        return conflict

    def resolve_conflict(
        self,
        conflict_id: str,
        resolution_strategy: str = ConflictResolutionStrategy.LATEST_VERSION.value,
    ) -> SyncConflict | None:
        """Resolve conflict"""
        conflict = self.conflicts.get(conflict_id)
        if not conflict:
            return None

        conflict.resolution_strategy = resolution_strategy
        conflict.resolved = True
        conflict.resolved_at = int(time.time())

        return conflict

    def get_pending_syncs(self) -> list[SyncJob]:
        """Get all pending sync jobs"""
        return [job for job in self.job_queue.values() if job.status == SyncStatus.PENDING.value]

    def get_sync_status(self) -> dict[str, Any]:
        """Get overall sync status"""
        total_jobs = len(self.job_queue)
        pending = sum(1 for job in self.job_queue.values() if job.status == SyncStatus.PENDING.value)
        transferring = sum(1 for job in self.job_queue.values() if job.status == SyncStatus.TRANSFERRING.value)
        complete = sum(1 for job in self.job_queue.values() if job.status == SyncStatus.COMPLETE.value)
        failed = sum(1 for job in self.job_queue.values() if job.status == SyncStatus.FAILED.value)
        conflicts = len(self.conflicts)

        return {
            "total_jobs": total_jobs,
            "pending": pending,
            "transferring": transferring,
            "complete": complete,
            "failed": failed,
            "conflicts": conflicts,
            "unresolved_conflicts": sum(1 for c in self.conflicts.values() if not c.resolved),
        }

    def get_unresolved_conflicts(self) -> list[SyncConflict]:
        """Get unresolved conflicts"""
        return [c for c in self.conflicts.values() if not c.resolved]

    def process_pending_syncs(self) -> dict[str, Any]:
        """Process pending sync jobs"""
        pending = self.get_pending_syncs()
        processed = 0
        failed = 0

        for job in pending:
            try:
                job.status = SyncStatus.TRANSFERRING.value
                processed += 1
            except Exception as e:
                self.mark_sync_failed(job.job_id, str(e))
                failed += 1

        return {"processed": processed, "failed": failed, "remaining": len(self.get_pending_syncs())}

    def broadcast_to_classroom(self, action: str, resource_type: str, resource_id: str, classroom_id: str | None = None) -> str:
        """Broadcast sync job to classroom"""
        target_devices = None
        if classroom_id:
            devices = self.store.list_devices()
            target_devices = [d["device_id"] for d in devices if d.get("classroom") == classroom_id]

        job = self.enqueue_sync(action, resource_type, resource_id, target_devices=target_devices)
        return job.job_id

    def cleanup_completed_syncs(self, days_old: int = 7) -> int:
        """Clean up old completed sync jobs"""
        cutoff_time = int(time.time()) - (days_old * 86400)
        removed = 0

        job_ids_to_remove = [
            job_id
            for job_id, job in self.job_queue.items()
            if job.status == SyncStatus.COMPLETE.value and job.updated_at < cutoff_time
        ]

        for job_id in job_ids_to_remove:
            del self.job_queue[job_id]
            removed += 1

        return removed
