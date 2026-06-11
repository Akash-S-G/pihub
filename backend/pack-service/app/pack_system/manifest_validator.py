from __future__ import annotations

from typing import Any

from .checksum_generator import ChecksumGenerator
from .version_manager import VersionManager


class ManifestValidator:
    required_fields = (
        "pack_id",
        "version",
        "grade",
        "subject",
        "chapter",
        "language",
        "generated_at",
        "checksum",
        "retrieval_index_version",
        "artifact_counts",
        "generation_metadata",
    )

    def validate(self, manifest: dict[str, Any]) -> tuple[bool, list[str]]:
        errors: list[str] = []
        for field_name in self.required_fields:
            if field_name not in manifest:
                errors.append(f"missing:{field_name}")

        version = manifest.get("version")
        if isinstance(version, str):
            try:
                VersionManager.normalize(version)
            except ValueError as exc:
                errors.append(str(exc))
        else:
            errors.append("version:not-a-string")

        artifact_counts = manifest.get("artifact_counts") or {}
        if not isinstance(artifact_counts, dict):
            errors.append("artifact_counts:not-a-dict")
        else:
            for key, value in artifact_counts.items():
                if not isinstance(value, int) or value < 0:
                    errors.append(f"artifact_counts.invalid:{key}")

        checksum = manifest.get("checksum")
        if checksum:
            checksum_source = {key: value for key, value in manifest.items() if key != "checksum"}
            if checksum != ChecksumGenerator.checksum_dict(checksum_source):
                errors.append("checksum:mismatch")

        return not errors, errors
