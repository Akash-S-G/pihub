from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.manifest.validator import ExperimentManifestValidator
from app.models.manifest_storage import (
    BuilderManifestDetail,
    BuilderManifestMutationResponse,
    BuilderManifestRevisionDetail,
    BuilderManifestRevisionSummary,
    BuilderManifestSummary,
    CreateBuilderManifestRequest,
    ExperimentStatus,
    UpdateBuilderManifestRequest,
)
from app.services.manifest_migration_service import ManifestMigrationError, ManifestMigrationService
from app.services.manifest_version_service import ManifestVersionService
from app.storage.manifest_storage_repository import ManifestStorageRepository
from app.core.observability import operation_span


logger = logging.getLogger("experiment-service.builder")


class BuilderManifestNotFoundError(ValueError):
    pass


class BuilderManifestValidationError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


class BuilderManifestStateError(ValueError):
    pass


class ManifestStorageService:
    def __init__(
        self,
        repository: ManifestStorageRepository | None = None,
        validator: ExperimentManifestValidator | None = None,
        version_service: ManifestVersionService | None = None,
        migration_service: ManifestMigrationService | None = None,
    ) -> None:
        self.repository = repository or ManifestStorageRepository()
        self.validator = validator or ExperimentManifestValidator()
        self.version_service = version_service or ManifestVersionService()
        self.migration_service = migration_service or ManifestMigrationService()

    def create_draft(self, request: CreateBuilderManifestRequest) -> BuilderManifestMutationResponse:
        logger.info("[BUILDER] MANIFEST_CREATE owner_id=%s", request.owner_id)
        with operation_span("create_manifest"):
            manifest = self._prepare_manifest(request.manifest)
            manifest_id = str(uuid4())
            created_at = self._now()
            record = self.repository.create(
                manifest_id=manifest_id,
                owner_id=request.owner_id,
                title=request.title,
                manifest=manifest,
                execution=self._execution(manifest),
                created_at=created_at,
            )
        logger.info("[BUILDER] REVISION_CREATED manifest_id=%s revision=1", manifest_id)
        logger.info("[BUILDER] STORAGE_SUCCESS manifest_id=%s", manifest_id)
        return BuilderManifestMutationResponse(
            manifest_id=record["id"],
            revision=int(record["current_revision"]),
            status=ExperimentStatus(record["status"]),
        )

    def update_draft(self, manifest_id: str, request: UpdateBuilderManifestRequest) -> BuilderManifestMutationResponse:
        logger.info("[BUILDER] MANIFEST_UPDATE manifest_id=%s", manifest_id)
        with operation_span("update_manifest", manifest_id=manifest_id):
            existing = self.repository.get(manifest_id)
            if existing is None:
                raise BuilderManifestNotFoundError(f"Manifest not found: {manifest_id}")
            if existing["status"] != ExperimentStatus.DRAFT.value:
                raise BuilderManifestStateError("Only draft manifests can be updated")

            manifest = self._prepare_manifest(request.manifest)
            updated = self.repository.update(
                manifest_id=manifest_id,
                owner_id=request.owner_id,
                title=request.title,
                manifest=manifest,
                execution=self._execution(manifest),
                updated_at=self._now(),
            )
        if updated is None:
            raise BuilderManifestNotFoundError(f"Manifest not found: {manifest_id}")
        logger.info("[BUILDER] REVISION_CREATED manifest_id=%s revision=%s", manifest_id, updated["current_revision"])
        logger.info("[BUILDER] STORAGE_SUCCESS manifest_id=%s", manifest_id)
        return BuilderManifestMutationResponse(
            manifest_id=updated["id"],
            revision=int(updated["current_revision"]),
            status=ExperimentStatus(updated["status"]),
        )

    def get_manifest(self, manifest_id: str) -> BuilderManifestDetail:
        record = self.repository.get(manifest_id)
        if record is None:
            raise BuilderManifestNotFoundError(f"Manifest not found: {manifest_id}")
        revision = self.repository.load_revision(manifest_id, int(record["current_revision"]))
        if revision is None:
            raise BuilderManifestNotFoundError(f"Current revision not found for manifest: {manifest_id}")
        return self._detail(record, revision)

    def list_manifests(self, owner_id: str | None = None) -> list[BuilderManifestSummary]:
        return [self._summary(record) for record in self.repository.list(owner_id)]

    def publish(self, manifest_id: str) -> BuilderManifestMutationResponse:
        logger.info("[BUILDER] MANIFEST_PUBLISH manifest_id=%s", manifest_id)
        with operation_span("publish_manifest", manifest_id=manifest_id):
            record = self.repository.publish(manifest_id, self._now())
        if record is None:
            raise BuilderManifestNotFoundError(f"Manifest not found: {manifest_id}")
        logger.info("[BUILDER] STORAGE_SUCCESS manifest_id=%s", manifest_id)
        return BuilderManifestMutationResponse(
            manifest_id=record["id"],
            revision=int(record["current_revision"]),
            status=ExperimentStatus(record["status"]),
        )

    def archive(self, manifest_id: str) -> BuilderManifestMutationResponse:
        logger.info("[BUILDER] MANIFEST_ARCHIVE manifest_id=%s", manifest_id)
        with operation_span("archive_manifest", manifest_id=manifest_id):
            record = self.repository.archive(manifest_id, self._now())
        if record is None:
            raise BuilderManifestNotFoundError(f"Manifest not found: {manifest_id}")
        logger.info("[BUILDER] STORAGE_SUCCESS manifest_id=%s", manifest_id)
        return BuilderManifestMutationResponse(
            manifest_id=record["id"],
            revision=int(record["current_revision"]),
            status=ExperimentStatus(record["status"]),
        )

    def revision_history(self, manifest_id: str) -> list[BuilderManifestRevisionSummary]:
        if self.repository.get(manifest_id) is None:
            raise BuilderManifestNotFoundError(f"Manifest not found: {manifest_id}")
        return [self._revision_summary(row) for row in self.repository.revisions(manifest_id)]

    def revision_detail(self, manifest_id: str, revision: int) -> BuilderManifestRevisionDetail:
        row = self.repository.load_revision(manifest_id, revision)
        if row is None:
            raise BuilderManifestNotFoundError(f"Revision not found: {manifest_id} revision {revision}")
        return BuilderManifestRevisionDetail(
            id=row["id"],
            manifest_id=row["manifest_id"],
            revision=int(row["revision"]),
            created_at=row["created_at"],
            created_by=row.get("created_by"),
            manifest=row["manifest"],
            execution=row.get("execution"),
        )

    def _prepare_manifest(self, manifest: dict[str, Any]) -> dict[str, Any]:
        candidate = dict(manifest)
        initial_validation = self.validator.validate(candidate)
        if not initial_validation.valid:
            logger.info("[BUILDER] VALIDATION_FAILED errors=%s", initial_validation.errors)
            raise BuilderManifestValidationError(initial_validation.errors)

        compatibility = self.version_service.check_compatibility(candidate)
        if compatibility["migration_required"]:
            try:
                migration = self.migration_service.migrate(candidate, compatibility["target_version"])
            except ManifestMigrationError as exc:
                logger.info("[BUILDER] VALIDATION_FAILED errors=%s", [str(exc)])
                raise BuilderManifestValidationError([str(exc)]) from exc
            candidate = migration["manifest"]

        validation = self.validator.validate(candidate)
        if not validation.valid:
            logger.info("[BUILDER] VALIDATION_FAILED errors=%s", validation.errors)
            raise BuilderManifestValidationError(validation.errors)
        return candidate

    def _summary(self, record: dict[str, Any]) -> BuilderManifestSummary:
        return BuilderManifestSummary(
            manifest_id=record["id"],
            owner_id=record.get("owner_id"),
            title=record.get("title") or "",
            description=record.get("description"),
            subject=record.get("subject"),
            status=ExperimentStatus(record["status"]),
            manifest_version=record.get("manifest_version") or "unknown",
            current_revision=int(record["current_revision"]),
            content_hash=record.get("content_hash"),
            manifest_hash=record.get("manifest_hash") or record.get("content_hash"),
            created_at=record["created_at"],
            updated_at=record["updated_at"],
            tags=record.get("tags", []),
        )

    def _detail(self, record: dict[str, Any], revision: dict[str, Any]) -> BuilderManifestDetail:
        summary = self._summary(record)
        return BuilderManifestDetail(
            **self._dump(summary),
            manifest=revision["manifest"],
            execution=revision.get("execution"),
        )

    def _revision_summary(self, row: dict[str, Any]) -> BuilderManifestRevisionSummary:
        return BuilderManifestRevisionSummary(
            id=row["id"],
            manifest_id=row["manifest_id"],
            revision=int(row["revision"]),
            revision_hash=row.get("revision_hash"),
            created_at=row["created_at"],
            created_by=row.get("created_by"),
        )

    def _execution(self, manifest: dict[str, Any]) -> dict[str, Any] | None:
        execution = manifest.get("execution")
        return execution if isinstance(execution, dict) else None

    def _dump(self, model: Any) -> dict[str, Any]:
        if hasattr(model, "model_dump"):
            return model.model_dump(mode="json")
        return model.dict()

    def _now(self) -> str:
        return datetime.now(UTC).isoformat()
