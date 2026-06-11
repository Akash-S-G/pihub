from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


SHARE_VERSION = "1.0.0"


class TrustLevel(StrEnum):
    TRUSTED_AUTHOR = "trusted_author"
    TRUSTED_NODE = "trusted_node"
    UNKNOWN_SOURCE = "unknown_source"


class SharingMetadata(BaseModel):
    author: str = ""
    created_at: str = ""
    source_node: str = ""
    trust_level: TrustLevel = TrustLevel.UNKNOWN_SOURCE


class SharingSignature(BaseModel):
    package_hash: str = ""
    manifest_hash: str = ""
    revision_hash: str = ""
    signature: str = ""
    algorithm: str = "sha256"


class SharePackage(BaseModel):
    share_version: str = SHARE_VERSION
    manifest: dict[str, Any]
    revision: dict[str, Any] = Field(default_factory=dict)
    revision_history: list[dict[str, Any]] = Field(default_factory=list)
    assets: list[dict[str, Any]] = Field(default_factory=list)
    metadata: SharingMetadata = Field(default_factory=SharingMetadata)
    signature: str = ""
    hashes: SharingSignature = Field(default_factory=SharingSignature)


class ShareExportRequest(BaseModel):
    manifest_id: str
    revision: int | None = None
    author: str = ""
    source_node: str = ""


class ShareImportRequest(BaseModel):
    package: SharePackage
    owner_id: str = "imported"


class ShareImportResponse(BaseModel):
    imported: bool
    manifest_id: str | None = None
    status: str = "draft"
    revision: int | None = None
    trust_level: TrustLevel = TrustLevel.UNKNOWN_SOURCE
    verification: dict[str, Any] = Field(default_factory=dict)


class ShareVerifyRequest(BaseModel):
    package: SharePackage


class ShareVerifyResponse(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    package_hash: str = ""
    manifest_hash: str = ""
    revision_hash: str = ""
    trust_level: TrustLevel = TrustLevel.UNKNOWN_SOURCE


class ShareSignRequest(BaseModel):
    package: SharePackage


class ShareTrustRequest(BaseModel):
    source_type: str
    source_id: str
    trusted: bool = True


class SharingAnalytics(BaseModel):
    imports: int = 0
    exports: int = 0
    trusted_sources: int = 0
    verification_failures: int = 0
