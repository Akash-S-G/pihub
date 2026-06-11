from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.manifest.manifest_service import ExperimentManifestService
from app.models.manifest_storage import ExperimentStatus
from app.storage.manifest_storage_repository import ManifestStorageRepository


class ManifestResolverError(ValueError):
    pass


class ManifestNotFoundError(ManifestResolverError):
    pass


class ManifestUnavailableError(ManifestResolverError):
    pass


class ManifestHashMismatchError(ManifestResolverError):
    pass


@dataclass(frozen=True)
class ResolvedManifest:
    manifest_id: str
    source: str
    manifest: dict[str, Any]
    execution: dict[str, Any] | None
    revision: int | None = None
    manifest_hash: str | None = None
    revision_hash: str | None = None


class ManifestResolver:
    def __init__(
        self,
        manifest_service: ExperimentManifestService | None = None,
        builder_repository: ManifestStorageRepository | None = None,
    ) -> None:
        self.manifest_service = manifest_service or ExperimentManifestService()
        self.builder_repository = builder_repository or ManifestStorageRepository()

    def resolve(self, manifest_id: str, revision: int | None = None) -> ResolvedManifest:
        if not manifest_id.strip():
            raise ManifestNotFoundError("Manifest id is required")

        template = self._resolve_template(manifest_id)
        if template is not None:
            manifest = dict(template.manifest)
            execution = manifest.get("execution") if isinstance(manifest.get("execution"), dict) else None
            return ResolvedManifest(
                manifest_id=str(manifest.get("id") or manifest_id),
                source="template",
                manifest=manifest,
                execution=execution,
                revision=revision,
            )

        return self._resolve_builder_manifest(manifest_id, revision)

    def _resolve_template(self, manifest_id: str):
        direct = self.manifest_service.get_template(manifest_id)
        if direct is not None:
            return direct

        template_id = f"{manifest_id}-manifest-template"
        by_template_id = self.manifest_service.get_template(template_id)
        if by_template_id is not None:
            return by_template_id

        for template in self.manifest_service.list_templates():
            if str(template.manifest.get("id") or "") == manifest_id:
                return template
        return None

    def _resolve_builder_manifest(self, manifest_id: str, revision: int | None) -> ResolvedManifest:
        record = self.builder_repository.get(manifest_id)
        if record is None:
            raise ManifestNotFoundError(f"Manifest not found: {manifest_id}")
        if record["status"] != ExperimentStatus.PUBLISHED.value:
            raise ManifestUnavailableError(f"Manifest is not published: {manifest_id}")

        revision_number = revision or int(record["current_revision"])
        revision_record = self.builder_repository.load_revision(manifest_id, revision_number)
        if revision_record is None:
            raise ManifestNotFoundError(f"Revision not found: {manifest_id} revision {revision_number}")

        manifest = revision_record["manifest"]
        execution = revision_record.get("execution")
        if not isinstance(execution, dict):
            execution = manifest.get("execution") if isinstance(manifest.get("execution"), dict) else None

        manifest_hash = self.builder_repository.content_hash(manifest)
        stored_manifest_hash = record.get("manifest_hash") or record.get("content_hash")
        if revision is None and stored_manifest_hash and stored_manifest_hash != manifest_hash:
            raise ManifestHashMismatchError(f"manifest_hash mismatch for manifest: {manifest_id}")

        revision_hash = self.builder_repository.revision_hash(manifest, execution)
        stored_revision_hash = revision_record.get("revision_hash")
        if stored_revision_hash and stored_revision_hash != revision_hash:
            raise ManifestHashMismatchError(f"revision_hash mismatch for manifest: {manifest_id} revision {revision_number}")

        return ResolvedManifest(
            manifest_id=manifest_id,
            source="builder",
            manifest=manifest,
            execution=execution,
            revision=revision_number,
            manifest_hash=manifest_hash,
            revision_hash=revision_hash,
        )
