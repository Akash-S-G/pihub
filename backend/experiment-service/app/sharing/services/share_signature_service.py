from __future__ import annotations

import hashlib
import json
from typing import Any

from app.sharing.models import SharePackage, SharingSignature


class ShareSignatureService:
    SIGNATURE_PREFIX = "pihub-share"

    def sign(self, package: SharePackage) -> SharePackage:
        package_hash = self.package_hash(package)
        manifest_hash = self.hash_object(package.manifest)
        revision_hash = self.hash_object(
            {
                "revision": package.revision,
                "revision_history": package.revision_history,
                "assets": package.assets,
            }
        )
        signature = self._signature(package_hash, manifest_hash, revision_hash)
        package.signature = signature
        package.hashes = SharingSignature(
            package_hash=package_hash,
            manifest_hash=manifest_hash,
            revision_hash=revision_hash,
            signature=signature,
        )
        return package

    def verify_hashes(self, package: SharePackage) -> tuple[bool, list[str], SharingSignature]:
        expected = SharingSignature(
            package_hash=self.package_hash(package),
            manifest_hash=self.hash_object(package.manifest),
            revision_hash=self.hash_object(
                {
                    "revision": package.revision,
                    "revision_history": package.revision_history,
                    "assets": package.assets,
                }
            ),
        )
        expected.signature = self._signature(expected.package_hash, expected.manifest_hash, expected.revision_hash)
        errors: list[str] = []
        if package.hashes.package_hash and package.hashes.package_hash != expected.package_hash:
            errors.append("package_hash mismatch")
        if package.hashes.manifest_hash and package.hashes.manifest_hash != expected.manifest_hash:
            errors.append("manifest_hash mismatch")
        if package.hashes.revision_hash and package.hashes.revision_hash != expected.revision_hash:
            errors.append("revision_hash mismatch")
        signature = package.signature or package.hashes.signature
        if signature and signature != expected.signature:
            errors.append("signature mismatch")
        if not signature:
            errors.append("signature missing")
        return not errors, errors, expected

    def package_hash(self, package: SharePackage) -> str:
        payload = {
            "share_version": package.share_version,
            "manifest": package.manifest,
            "revision": package.revision,
            "revision_history": package.revision_history,
            "assets": package.assets,
            "metadata": self._dump(package.metadata),
        }
        return self.hash_object(payload)

    def hash_object(self, value: Any) -> str:
        return hashlib.sha256(self._canonical(value).encode("utf-8")).hexdigest()

    def _signature(self, package_hash: str, manifest_hash: str, revision_hash: str) -> str:
        payload = f"{self.SIGNATURE_PREFIX}:{package_hash}:{manifest_hash}:{revision_hash}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _canonical(self, value: Any) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

    def _dump(self, model: Any) -> dict[str, Any]:
        if hasattr(model, "model_dump"):
            return model.model_dump(mode="json")
        if hasattr(model, "dict"):
            return model.dict()
        return dict(model)
