from __future__ import annotations

from typing import Any

from ..pack_system.version_manager import VersionManager


class UpdateResolver:
    def resolve(self, host_records: list[dict[str, Any]], current_versions: dict[str, str]) -> dict[str, Any]:
        host_index = {record["pack_id"]: record for record in host_records}
        packs_to_add: list[str] = []
        packs_to_update: list[str] = []
        packs_to_remove: list[str] = []
        priority: list[str] = []
        total_size = 0.0

        for pack_id in current_versions:
            if pack_id not in host_index:
                packs_to_remove.append(pack_id)

        for pack_id, record in host_index.items():
            host_version = str(record.get("version", "0.0.0"))
            current_version = current_versions.get(pack_id)
            if current_version is None:
                packs_to_add.append(pack_id)
                total_size += float(record.get("compressed_size_mb", record.get("size_mb", 0.0)) or 0.0)
            elif VersionManager.compare(current_version, host_version) < 0:
                packs_to_update.append(pack_id)
                total_size += float(record.get("compressed_size_mb", record.get("size_mb", 0.0)) or 0.0)

        for pack_id in packs_to_add + packs_to_update:
            if any(token in pack_id.lower() for token in ("grade", "subject", "chapter")):
                priority.insert(0, pack_id)
            else:
                priority.append(pack_id)

        return {
            "packs_to_add": packs_to_add,
            "packs_to_update": packs_to_update,
            "packs_to_remove": packs_to_remove,
            "sync_priority": priority,
            "total_download_size_mb": round(total_size, 4),
        }
