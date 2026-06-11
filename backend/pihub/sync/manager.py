from __future__ import annotations

import io
import hashlib
import os
import zipfile
from pathlib import Path
from typing import Any


def validate_pack_file(file_name: str, data: bytes) -> None:
    if not file_name.lower().endswith((".zip", ".pack")):
        raise ValueError("Packs must be packaged as .zip or .pack files")
    if len(data) > 1024 * 1024 * 1024:
        raise ValueError("Pack too large for PiHub cache")
    if file_name.lower().endswith(".zip") and not zipfile.is_zipfile(io.BytesIO(data)):
        raise ValueError("Invalid zip pack file")


def checksum_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_sync_manifest(session: dict[str, Any]) -> dict[str, Any]:
    return {
        "session_id": session["session_id"],
        "resource_type": session.get("resource_type"),
        "resource_id": session.get("resource_id"),
        "offset_bytes": session.get("offset_bytes", 0),
        "total_bytes": session.get("total_bytes"),
        "status": session.get("status"),
        "retry_count": session.get("retry_count", 0),
        "metadata": session.get("metadata", {}),
    }
