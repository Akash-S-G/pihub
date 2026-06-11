from __future__ import annotations

import logging
from typing import Any

from .models import CURRENT_MANIFEST_VERSION, CompatibilityResult, MigrationResult


logger = logging.getLogger("experiment-service.manifest")


class ManifestCompatibilityService:
    DEPRECATED_FIELDS = {"mode", "sensor_type"}

    def check(self, manifest: dict[str, Any]) -> CompatibilityResult:
        logger.info("[MANIFEST] COMPATIBILITY_CHECK")
        version = manifest.get("manifest_version") if isinstance(manifest, dict) else None
        deprecated_fields = sorted(field for field in self.DEPRECATED_FIELDS if isinstance(manifest, dict) and field in manifest)
        recommendations: list[str] = []
        warnings: list[str] = []
        compatible = version == CURRENT_MANIFEST_VERSION
        if version is None:
            compatible = False
            recommendations.append("Add manifest_version before using this manifest.")
        elif version != CURRENT_MANIFEST_VERSION:
            recommendations.append(f"Run manifest migration from {version} to {CURRENT_MANIFEST_VERSION}.")
        if deprecated_fields:
            warnings.append(f"Deprecated fields present: {', '.join(deprecated_fields)}")
        return CompatibilityResult(
            compatible=compatible and not deprecated_fields,
            manifest_version=str(version) if version is not None else None,
            deprecated_fields=deprecated_fields,
            migration_recommendations=recommendations,
            warnings=warnings,
        )


class ManifestMigrationService:
    def migrate(self, manifest: dict[str, Any], target_version: str = CURRENT_MANIFEST_VERSION) -> MigrationResult:
        logger.info("[MANIFEST] MIGRATION_REQUEST")
        from_version = manifest.get("manifest_version") if isinstance(manifest, dict) else None
        migrated_manifest = dict(manifest)
        warnings: list[str] = []
        if from_version is None:
            migrated_manifest["manifest_version"] = target_version
            warnings.append("manifest_version was missing and has been set to target version.")
        elif from_version != target_version:
            warnings.append("No concrete migrations are available yet; manifest returned unchanged.")
        return MigrationResult(
            migrated=from_version != target_version,
            from_version=str(from_version) if from_version is not None else None,
            to_version=target_version,
            manifest=migrated_manifest,
            warnings=warnings,
        )
