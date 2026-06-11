from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from app.manifest.models import CURRENT_MANIFEST_VERSION


logger = logging.getLogger("experiment-service.manifest_migration")

MigrationFunction = Callable[[dict[str, Any]], dict[str, Any]]


class ManifestMigrationError(ValueError):
    pass


def migrate_090_to_100(manifest: dict[str, Any]) -> dict[str, Any]:
    migrated = dict(manifest)
    migrated["manifest_version"] = CURRENT_MANIFEST_VERSION
    return migrated


MIGRATION_REGISTRY: dict[tuple[str, str], MigrationFunction] = {
    ("0.9.0", CURRENT_MANIFEST_VERSION): migrate_090_to_100,
}


class ManifestMigrationService:
    def migrate(self, manifest: dict[str, Any], target_version: str = CURRENT_MANIFEST_VERSION) -> dict[str, Any]:
        logger.info("[MANIFEST] MIGRATION_START")
        source_version = self._source_version(manifest)
        logger.info("[MANIFEST] SOURCE_VERSION=%s", source_version)
        logger.info("[MANIFEST] TARGET_VERSION=%s", target_version)
        try:
            if not isinstance(manifest, dict):
                raise ManifestMigrationError("Manifest must be an object")
            if source_version == target_version:
                logger.info("[MANIFEST] MIGRATION_SUCCESS")
                return {
                    "success": True,
                    "source_version": source_version,
                    "target_version": target_version,
                    "manifest": dict(manifest),
                }

            migration = MIGRATION_REGISTRY.get((source_version, target_version))
            if migration is None:
                raise ManifestMigrationError(f"No migration registered from {source_version} to {target_version}")

            migrated_manifest = migration(manifest)
            logger.info("[MANIFEST] MIGRATION_SUCCESS")
            return {
                "success": True,
                "source_version": source_version,
                "target_version": target_version,
                "manifest": migrated_manifest,
            }
        except Exception as exc:
            logger.error("[MANIFEST] MIGRATION_FAILED error=%s", exc)
            raise

    def _source_version(self, manifest: dict[str, Any]) -> str:
        if not isinstance(manifest, dict):
            return "unknown"
        version = manifest.get("manifest_version")
        if version is None:
            return "unknown"
        return str(version)
