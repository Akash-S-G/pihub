from __future__ import annotations

import logging
import re
from typing import Any

from app.manifest.models import CURRENT_MANIFEST_VERSION


logger = logging.getLogger("experiment-service.manifest_version")

SUPPORTED_MANIFEST_VERSIONS = [
    CURRENT_MANIFEST_VERSION,
]

SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")


class ManifestVersionService:
    def versions(self) -> dict[str, Any]:
        return {
            "current_version": CURRENT_MANIFEST_VERSION,
            "supported_versions": list(SUPPORTED_MANIFEST_VERSIONS),
        }

    def check_compatibility(self, manifest: dict[str, Any]) -> dict[str, Any]:
        logger.info("[MANIFEST] VERSION_CHECK")
        manifest_version = self._manifest_version(manifest)
        supported = manifest_version in SUPPORTED_MANIFEST_VERSIONS
        migration_required = manifest_version != CURRENT_MANIFEST_VERSION
        return {
            "manifest_version": manifest_version,
            "supported": supported,
            "migration_required": migration_required,
            "target_version": CURRENT_MANIFEST_VERSION,
        }

    def validate_version(self, version: str) -> bool:
        return bool(SEMVER_PATTERN.match(version))

    def _manifest_version(self, manifest: dict[str, Any]) -> str:
        if not isinstance(manifest, dict):
            return "unknown"
        version = manifest.get("manifest_version")
        if version is None:
            return "unknown"
        return str(version)
