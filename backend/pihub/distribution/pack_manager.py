"""
Educational Pack Distribution Service

Handles:
- Pack manifests
- Version tracking
- Chunked transfers
- Classroom broadcasting
- Transfer monitoring
- Local pack indexing
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class PackManifest:
    """Educational pack manifest"""

    manifest_id: str
    pack_id: str
    pack_name: str
    version: str
    subject: str | None = None
    grade: int | None = None
    chapter: str | None = None
    file_size: int = 0
    file_checksum: str = ""
    chunk_size: int = 1024 * 1024
    total_chunks: int = 0
    created_at: int = 0
    metadata: dict[str, Any] | None = None

    def get_chunks(self) -> int:
        """Get total number of chunks"""
        if self.file_size == 0:
            return 0
        return (self.file_size + self.chunk_size - 1) // self.chunk_size


@dataclass
class PackTransfer:
    """Pack transfer session"""

    transfer_id: str
    pack_id: str
    device_id: str
    manifest_id: str
    status: str = "pending"
    bytes_transferred: int = 0
    chunks_received: list[int] | None = None
    started_at: int = 0
    completed_at: int = 0
    error_message: str | None = None
    retry_count: int = 0

    def get_progress(self) -> float:
        """Get transfer progress percentage"""
        if not chunks_received:
            return 0.0
        manifest = asdict(self)
        total_chunks = manifest.get("total_chunks", 1)
        return (len(self.chunks_received) / total_chunks) * 100 if total_chunks > 0 else 0.0


class PackDistributionManager:
    """Real educational pack distribution"""

    def __init__(self, store: Any, storage_dir: Path) -> None:
        self.store = store
        self.storage_dir = storage_dir
        self.manifests: dict[str, PackManifest] = {}
        self.transfers: dict[str, PackTransfer] = {}
        self.broadcast_logs: dict[str, dict[str, Any]] = {}

    def create_pack_manifest(
        self,
        pack_id: str,
        pack_name: str,
        version: str,
        file_size: int,
        file_checksum: str,
        subject: str | None = None,
        grade: int | None = None,
        chapter: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> PackManifest:
        """Create pack manifest"""
        manifest_id = str(uuid.uuid4())
        chunk_size = 1024 * 1024

        manifest = PackManifest(
            manifest_id=manifest_id,
            pack_id=pack_id,
            pack_name=pack_name,
            version=version,
            subject=subject,
            grade=grade,
            chapter=chapter,
            file_size=file_size,
            file_checksum=file_checksum,
            chunk_size=chunk_size,
            total_chunks=(file_size + chunk_size - 1) // chunk_size,
            created_at=int(time.time()),
            metadata=metadata,
        )

        self.manifests[manifest_id] = manifest
        return manifest

    def get_manifest(self, manifest_id: str) -> PackManifest | None:
        """Get pack manifest"""
        return self.manifests.get(manifest_id)

    def create_transfer(self, pack_id: str, device_id: str, manifest_id: str) -> PackTransfer:
        """Create new pack transfer session"""
        transfer_id = str(uuid.uuid4())
        manifest = self.manifests.get(manifest_id)

        transfer = PackTransfer(
            transfer_id=transfer_id,
            pack_id=pack_id,
            device_id=device_id,
            manifest_id=manifest_id,
            started_at=int(time.time()),
            chunks_received=[],
        )

        self.transfers[transfer_id] = transfer
        return transfer

    def update_transfer_chunk(self, transfer_id: str, chunk_index: int, chunk_data: bytes) -> PackTransfer | None:
        """Record chunk received"""
        transfer = self.transfers.get(transfer_id)
        if not transfer:
            return None

        if transfer.chunks_received is None:
            transfer.chunks_received = []

        if chunk_index not in transfer.chunks_received:
            transfer.chunks_received.append(chunk_index)
            transfer.bytes_transferred += len(chunk_data)

        manifest = self.manifests.get(transfer.manifest_id)
        if manifest and len(transfer.chunks_received) == manifest.total_chunks:
            transfer.status = "complete"
            transfer.completed_at = int(time.time())

        return transfer

    def get_transfer_status(self, transfer_id: str) -> dict[str, Any] | None:
        """Get transfer status"""
        transfer = self.transfers.get(transfer_id)
        if not transfer:
            return None

        manifest = self.manifests.get(transfer.manifest_id)
        return {
            "transfer_id": transfer_id,
            "pack_id": transfer.pack_id,
            "device_id": transfer.device_id,
            "status": transfer.status,
            "progress_percent": transfer.get_progress(),
            "bytes_transferred": transfer.bytes_transferred,
            "total_bytes": manifest.file_size if manifest else 0,
            "chunks_received": len(transfer.chunks_received) if transfer.chunks_received else 0,
            "total_chunks": manifest.total_chunks if manifest else 0,
        }

    def broadcast_pack_to_classroom(
        self,
        pack_id: str,
        classroom_id: str,
        grade_filter: int | None = None,
        subject_filter: str | None = None,
    ) -> dict[str, Any]:
        """Broadcast pack to classroom"""
        broadcast_id = str(uuid.uuid4())

        devices = self.store.list_devices()
        target_devices = []

        for device in devices:
            if device.get("classroom") != classroom_id:
                continue
            if grade_filter and device.get("metadata", {}).get("grade") != grade_filter:
                continue
            if subject_filter and device.get("metadata", {}).get("subject") != subject_filter:
                continue
            target_devices.append(device["device_id"])

        broadcast_log = {
            "broadcast_id": broadcast_id,
            "pack_id": pack_id,
            "classroom_id": classroom_id,
            "target_devices": target_devices,
            "created_at": int(time.time()),
            "status": "broadcasting",
            "total_devices": len(target_devices),
            "completed_transfers": 0,
            "failed_transfers": 0,
        }

        self.broadcast_logs[broadcast_id] = broadcast_log
        return broadcast_log

    def get_broadcast_status(self, broadcast_id: str) -> dict[str, Any] | None:
        """Get broadcast status"""
        return self.broadcast_logs.get(broadcast_id)

    def list_pack_versions(self, pack_id: str) -> list[dict[str, Any]]:
        """List all versions of pack"""
        versions = []
        for manifest in self.manifests.values():
            if manifest.pack_id == pack_id:
                versions.append(asdict(manifest))
        return sorted(versions, key=lambda x: x["created_at"], reverse=True)

    def validate_pack_integrity(self, pack_id: str, checksum: str) -> bool:
        """Validate pack integrity"""
        pack = self.store.get_pack(pack_id)
        if not pack:
            return False

        stored_checksum = pack.get("checksum", "")
        return stored_checksum == checksum

    def get_distribution_metrics(self, classroom_id: str) -> dict[str, Any]:
        """Get distribution metrics for classroom"""
        transfers = [t for t in self.transfers.values() if t.status == "complete"]
        pending = [t for t in self.transfers.values() if t.status == "pending"]
        failed = [t for t in self.transfers.values() if t.status == "failed"]

        total_bytes = sum(t.bytes_transferred for t in transfers)

        return {
            "classroom_id": classroom_id,
            "total_transfers": len(self.transfers),
            "completed_transfers": len(transfers),
            "pending_transfers": len(pending),
            "failed_transfers": len(failed),
            "total_bytes_transferred": total_bytes,
            "avg_transfer_time": sum(
                (t.completed_at - t.started_at) for t in transfers if t.completed_at and t.started_at
            )
            // len(transfers)
            if transfers
            else 0,
        }
