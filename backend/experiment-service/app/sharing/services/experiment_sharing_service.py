from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.manifest.validator import ExperimentManifestValidator
from app.models.manifest_storage import ExperimentStatus
from app.services.manifest_version_service import ManifestVersionService
from app.sharing.models import (
    SHARE_VERSION,
    ShareExportRequest,
    ShareImportRequest,
    ShareImportResponse,
    SharePackage,
    ShareTrustRequest,
    ShareVerifyResponse,
    SharingAnalytics,
    SharingMetadata,
    TrustLevel,
)
from app.sharing.repositories.sharing_repository import SharingRepository
from app.sharing.services.share_signature_service import ShareSignatureService
from app.storage.manifest_storage_repository import ManifestStorageRepository
from app.core.observability import operation_span


logger = logging.getLogger("experiment-service.sharing")


class SharingError(ValueError):
    pass


class SharingNotFoundError(SharingError):
    pass


class SharingValidationError(SharingError):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


class ExperimentSharingService:
    FORBIDDEN_KEYS = {
        "code",
        "source_code",
        "python",
        "flutter",
        "runtime",
        "runtime_state",
        "sensor_state",
        "execution_session",
        "simulation_engine",
        "physics_engine",
    }

    def __init__(
        self,
        manifest_repository: ManifestStorageRepository | None = None,
        sharing_repository: SharingRepository | None = None,
        signature_service: ShareSignatureService | None = None,
        validator: ExperimentManifestValidator | None = None,
        compatibility: ManifestVersionService | None = None,
    ) -> None:
        self.manifest_repository = manifest_repository or ManifestStorageRepository()
        self.sharing_repository = sharing_repository or SharingRepository()
        self.signature_service = signature_service or ShareSignatureService()
        self.validator = validator or ExperimentManifestValidator()
        self.compatibility = compatibility or ManifestVersionService()

    def export_package(self, request: ShareExportRequest) -> SharePackage:
        logger.info("[SHARING] EXPORT_START manifest_id=%s", request.manifest_id)
        with operation_span("export_package", manifest_id=request.manifest_id, revision=request.revision):
            record = self.manifest_repository.get(request.manifest_id)
            if record is None:
                raise SharingNotFoundError(f"Manifest not found: {request.manifest_id}")
            if record["status"] != ExperimentStatus.PUBLISHED.value:
                raise SharingValidationError(["Only published manifests can be exported"])

            revision_number = request.revision or int(record["current_revision"])
            revision = self.manifest_repository.load_revision(request.manifest_id, revision_number)
            if revision is None:
                raise SharingNotFoundError(f"Revision not found: {request.manifest_id} revision {revision_number}")
            history = [self.manifest_repository.load_revision(request.manifest_id, item["revision"]) for item in self.manifest_repository.revisions(request.manifest_id)]
            revision_history = [self._revision_payload(item) for item in history if item is not None]
            manifest = self._sanitize(revision["manifest"])

        package = SharePackage(
            share_version=SHARE_VERSION,
            manifest=manifest,
            revision=self._revision_payload(revision),
            revision_history=revision_history,
            assets=[],
            metadata=SharingMetadata(
                author=request.author or str(record.get("owner_id") or ""),
                created_at=self._now(),
                source_node=request.source_node,
                trust_level=self._trust_level(request.author or str(record.get("owner_id") or ""), request.source_node),
            ),
        )
        signed = self.signature_service.sign(package)
        self.sharing_repository.record_package_hash(
            package_hash=signed.hashes.package_hash,
            manifest_hash=signed.hashes.manifest_hash,
            revision_hash=signed.hashes.revision_hash,
            direction="export",
            manifest_id=request.manifest_id,
            recorded_at=self._now(),
        )
        self.sharing_repository.increment("exports")
        logger.info("[SHARING] EXPORT_SUCCESS manifest_id=%s revision=%s", request.manifest_id, revision_number)
        return signed

    def import_package(self, request: ShareImportRequest) -> ShareImportResponse:
        logger.info("[SHARING] IMPORT_START")
        with operation_span("import_package"):
            verification = self.verify_package(request.package)
        if not verification.valid:
            raise SharingValidationError(verification.errors)

        manifest = self._sanitize(request.package.manifest)
        validation_errors = self._validate_manifest(manifest)
        if validation_errors:
            raise SharingValidationError(validation_errors)

        existing = self.manifest_repository.find_by_manifest_hash(verification.manifest_hash)
        if existing is not None:
            self.sharing_repository.record_package_hash(
                package_hash=verification.package_hash,
                manifest_hash=verification.manifest_hash,
                revision_hash=verification.revision_hash,
                direction="import",
                manifest_id=existing["id"],
                recorded_at=self._now(),
            )
            logger.info("[SHARING] IMPORT_DEDUPED manifest_id=%s package_hash=%s", existing["id"], verification.package_hash)
            return ShareImportResponse(
                imported=False,
                manifest_id=existing["id"],
                status=existing["status"],
                revision=int(existing["current_revision"]),
                trust_level=verification.trust_level,
                verification=self._dump(verification),
            )

        manifest_id = str(uuid4())
        revisions = request.package.revision_history or [request.package.revision]
        revisions = [self._import_revision(item, manifest) for item in revisions if isinstance(item, dict)]
        record = self.manifest_repository.import_draft(
            manifest_id=manifest_id,
            owner_id=request.owner_id,
            title=str(manifest.get("title") or "Imported Experiment"),
            manifest=manifest,
            revisions=revisions,
            created_at=self._now(),
        )
        self.sharing_repository.record_package_hash(
            package_hash=verification.package_hash,
            manifest_hash=verification.manifest_hash,
            revision_hash=verification.revision_hash,
            direction="import",
            manifest_id=record["id"],
            recorded_at=self._now(),
        )
        self.sharing_repository.increment("imports")
        logger.info("[SHARING] IMPORT_SUCCESS manifest_id=%s", manifest_id)
        return ShareImportResponse(
            imported=True,
            manifest_id=record["id"],
            status=record["status"],
            revision=int(record["current_revision"]),
            trust_level=verification.trust_level,
            verification=self._dump(verification),
        )

    def verify_package(self, package: SharePackage) -> ShareVerifyResponse:
        logger.info("[SHARING] VERIFY_START")
        errors: list[str] = []
        if package.share_version != SHARE_VERSION:
            errors.append(f"Unsupported share_version: {package.share_version}")
        if self._contains_forbidden(package.manifest):
            errors.append("Package contains forbidden executable or runtime fields")
        if any(self._contains_forbidden(item) for item in package.revision_history):
            errors.append("Revision history contains forbidden executable or runtime fields")

        hash_valid, hash_errors, hashes = self.signature_service.verify_hashes(package)
        errors.extend(hash_errors)

        manifest_errors = self._validate_manifest(self._sanitize(package.manifest))
        errors.extend(manifest_errors)
        trust_level = self._trust_level(package.metadata.author, package.metadata.source_node)
        valid = not errors and hash_valid
        if not valid:
            self.sharing_repository.increment("verification_failures")
        logger.info("[SHARING] VERIFY_END valid=%s errors=%s", valid, len(errors))
        return ShareVerifyResponse(
            valid=valid,
            errors=errors,
            package_hash=hashes.package_hash,
            manifest_hash=hashes.manifest_hash,
            revision_hash=hashes.revision_hash,
            trust_level=trust_level,
        )

    def sign_package(self, package: SharePackage) -> SharePackage:
        return self.signature_service.sign(package)

    def trust(self, request: ShareTrustRequest) -> dict[str, Any]:
        result = self.sharing_repository.set_trust(request.source_type, request.source_id, request.trusted, self._now())
        return result

    def analytics(self) -> SharingAnalytics:
        return SharingAnalytics(**self.sharing_repository.analytics())

    def _validate_manifest(self, manifest: dict[str, Any]) -> list[str]:
        compatibility = self.compatibility.check_compatibility(manifest)
        errors: list[str] = []
        if not compatibility.get("supported"):
            errors.append(f"Unsupported manifest version: {compatibility.get('manifest_version')}")
        validation = self.validator.validate(manifest)
        errors.extend(validation.errors)
        return errors

    def _revision_payload(self, revision: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": revision.get("id"),
            "manifest_id": revision.get("manifest_id"),
            "revision": revision.get("revision"),
            "manifest": self._sanitize(revision.get("manifest") if isinstance(revision.get("manifest"), dict) else {}),
            "execution": None,
            "created_at": revision.get("created_at"),
            "created_by": revision.get("created_by"),
        }

    def _import_revision(self, item: dict[str, Any], fallback_manifest: dict[str, Any]) -> dict[str, Any]:
        return {
            "revision": int(item.get("revision", 1)),
            "manifest": self._sanitize(item.get("manifest") if isinstance(item.get("manifest"), dict) else fallback_manifest),
            "execution": None,
            "created_at": item.get("created_at") or self._now(),
            "created_by": item.get("created_by"),
        }

    def _trust_level(self, author: str, source_node: str) -> TrustLevel:
        if self.sharing_repository.is_trusted("author", author):
            return TrustLevel.TRUSTED_AUTHOR
        if self.sharing_repository.is_trusted("node", source_node):
            return TrustLevel.TRUSTED_NODE
        return TrustLevel.UNKNOWN_SOURCE

    def _sanitize(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: self._sanitize(item) for key, item in value.items() if str(key).lower() not in self.FORBIDDEN_KEYS}
        if isinstance(value, list):
            return [self._sanitize(item) for item in value]
        return value

    def _contains_forbidden(self, value: Any) -> bool:
        if isinstance(value, dict):
            return any(str(key).lower() in self.FORBIDDEN_KEYS or self._contains_forbidden(item) for key, item in value.items())
        if isinstance(value, list):
            return any(self._contains_forbidden(item) for item in value)
        return False

    def _dump(self, model: Any) -> dict[str, Any]:
        if hasattr(model, "model_dump"):
            return model.model_dump(mode="json")
        if hasattr(model, "dict"):
            return model.dict()
        return dict(model)

    def _now(self) -> str:
        return datetime.now(UTC).isoformat()
