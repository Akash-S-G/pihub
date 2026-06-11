from __future__ import annotations

from typing import Any

from ..pack_system.checksum_generator import ChecksumGenerator


class SyncManifestGenerator:
    def generate(self, host_version: str, pack_records: list[dict[str, Any]]) -> dict[str, Any]:
        entries: list[dict[str, Any]] = []
        for record in pack_records:
            entry = {
                "pack_id": record.get("pack_id"),
                "version": record.get("version"),
                "checksum": record.get("checksum"),
                "content_checksum": record.get("content_checksum"),
                "compressed_size_mb": float(record.get("compressed_size_mb", record.get("size_mb", 0.0)) or 0.0),
                "grade": record.get("grade"),
                "subject": record.get("subject"),
                "chapter": record.get("chapter"),
                "language": record.get("language"),
            }
            entries.append(entry)

        manifest = {
            "host_version": host_version,
            "packs": entries,
            "total_packs": len(entries),
            "total_size_mb": round(sum(entry["compressed_size_mb"] for entry in entries), 4),
        }
        manifest["checksum"] = ChecksumGenerator.checksum_dict(manifest)
        return manifest
