from __future__ import annotations

from typing import Any

from ..pack_system.version_manager import VersionManager


class PackDiffEngine:
    def diff(self, local_manifest: dict[str, Any], remote_manifest: dict[str, Any]) -> dict[str, Any]:
        local_version = local_manifest.get("version", "0.0.0")
        remote_version = remote_manifest.get("version", "0.0.0")
        version_comparison = VersionManager.compare(local_version, remote_version)
        local_checksum = local_manifest.get("checksum")
        remote_checksum = remote_manifest.get("checksum")
        artifact_counts_local = local_manifest.get("artifact_counts", {})
        artifact_counts_remote = remote_manifest.get("artifact_counts", {})
        artifact_delta = {
            key: artifact_counts_remote.get(key, 0) - artifact_counts_local.get(key, 0)
            for key in sorted(set(artifact_counts_local) | set(artifact_counts_remote))
        }
        return {
            "version_comparison": version_comparison,
            "checksum_changed": local_checksum != remote_checksum,
            "artifact_delta": artifact_delta,
            "content_changed": local_manifest.get("content_checksum") != remote_manifest.get("content_checksum"),
        }
