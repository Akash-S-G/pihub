#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request
from io import BytesIO
from pathlib import Path
from typing import Any


REQUIRED_SYNC_FIELDS = {
    "pack_id",
    "version",
    "checksum",
    "size_bytes",
    "manifest_url",
    "download_url",
    "artifact_counts",
    "installable",
    "archive_exists",
    "manifest_exists",
}
REQUIRED_ARCHIVE_FILES = {"manifest.json", "content.json", "quizzes.json", "summaries.json", "glossary.json"}
NORMALIZED_ID_RE = re.compile(r"^[a-z0-9_]+$")


def request_bytes(base_url: str, path: str, timeout: float) -> tuple[int, dict[str, str], bytes]:
    url = f"{base_url.rstrip('/')}{path}"
    request = urllib.request.Request(url, headers={"Accept": "*/*"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read()
        return response.status, dict(response.headers), body


def request_json(base_url: str, path: str, timeout: float) -> tuple[dict[str, Any], dict[str, Any]]:
    status, headers, body = request_bytes(base_url, path, timeout)
    return json.loads(body.decode("utf-8")), {"status": status, "headers": headers, "body_bytes": len(body)}


def normalize_path(path: str) -> str:
    parsed = urllib.parse.urlparse(path)
    return parsed.path if parsed.scheme else path


def is_percent_encoded(path: str, pack_id: str) -> bool:
    return urllib.parse.quote(pack_id, safe="") in path


def archive_inventory(payload: bytes) -> dict[str, Any]:
    with tarfile.open(fileobj=BytesIO(payload), mode="r:gz") as archive:
        members = [member for member in archive.getmembers() if member.isfile()]
        files = {member.name.split("/", 1)[-1] for member in members}
        manifest_member = next((member for member in members if member.name.endswith("/manifest.json")), None)
        content_member = next((member for member in members if member.name.endswith("/content.json")), None)
        archive_manifest: dict[str, Any] = {}
        content_count = 0
        if manifest_member is not None:
            file_obj = archive.extractfile(manifest_member)
            if file_obj is not None:
                archive_manifest = json.loads(file_obj.read().decode("utf-8"))
        if content_member is not None:
            file_obj = archive.extractfile(content_member)
            if file_obj is not None:
                content = json.loads(file_obj.read().decode("utf-8"))
                content_count = len(content) if isinstance(content, list) else 0
        return {
            "files": sorted(files),
            "missing_required_files": sorted(REQUIRED_ARCHIVE_FILES - files),
            "manifest": archive_manifest,
            "content_count": content_count,
        }


def markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(cell).replace("\n", " ") for cell in row) + " |")
    return "\n".join(lines)


def checksum_match(sync_item: dict[str, Any], manifest: dict[str, Any], archive_manifest: dict[str, Any]) -> bool:
    sync_checksum = str(sync_item.get("checksum") or "")
    manifest_checksum = str((manifest.get("metadata") or {}).get("checksum") or manifest.get("checksum") or "")
    archive_checksum = str(archive_manifest.get("checksum") or "")
    return bool(sync_checksum) and sync_checksum == manifest_checksum == archive_checksum


def safe_get_json(base_url: str, path: str, timeout: float) -> tuple[dict[str, Any] | None, dict[str, Any], str | None]:
    try:
        body, meta = request_json(base_url, path, timeout)
        return body, meta, None
    except Exception as exc:  # noqa: BLE001 - audit report must capture exact failure
        return None, {}, str(exc)


def safe_get_bytes(base_url: str, path: str, timeout: float) -> tuple[bytes | None, dict[str, Any], str | None]:
    try:
        status, headers, body = request_bytes(base_url, path, timeout)
        return body, {"status": status, "headers": headers, "body_bytes": len(body)}, None
    except Exception as exc:  # noqa: BLE001 - audit report must capture exact failure
        return None, {}, str(exc)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate /packs/sync as the authoritative PIHUB pack installation contract.")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--output-dir", default=".")
    parser.add_argument("--timeout", type=float, default=60.0)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    packs_response, packs_meta = request_json(args.base_url, "/packs", args.timeout)
    sync_response, sync_meta = request_json(args.base_url, "/packs/sync", args.timeout)
    packs = packs_response.get("packs", [])
    sync_packs = sync_response.get("packs", [])
    packs_by_id = {str(item.get("pack_id")): item for item in packs}

    missing_field_rows: list[dict[str, Any]] = []
    manifest_rows: list[dict[str, Any]] = []
    download_rows: list[dict[str, Any]] = []
    id_rows: list[dict[str, Any]] = []
    checksum_rows: list[dict[str, Any]] = []
    contract_rows: list[dict[str, Any]] = []

    seen_ids: set[str] = set()
    duplicate_ids: set[str] = set()
    sample_manifest: dict[str, Any] | None = None
    sample_download: dict[str, Any] | None = None

    for sync_item in sync_packs:
        pack_id = str(sync_item.get("pack_id") or "")
        missing_fields = sorted(field for field in REQUIRED_SYNC_FIELDS if sync_item.get(field) in (None, ""))
        if missing_fields:
            missing_field_rows.append({"pack_id": pack_id, "missing_fields": missing_fields})
        if pack_id in seen_ids:
            duplicate_ids.add(pack_id)
        seen_ids.add(pack_id)

        manifest_url = normalize_path(str(sync_item.get("manifest_url") or ""))
        download_url = normalize_path(str(sync_item.get("download_url") or ""))
        normalized = bool(NORMALIZED_ID_RE.fullmatch(pack_id))
        urls_encoded = is_percent_encoded(manifest_url, pack_id) and is_percent_encoded(download_url, pack_id)
        id_rows.append({
            "pack_id": pack_id,
            "normalized": normalized,
            "duplicate": pack_id in duplicate_ids,
            "urls_percent_encoded": urls_encoded,
            "manifest_url": manifest_url,
            "download_url": download_url,
            "classification": "NORMALIZED" if normalized and urls_encoded else "NON_NORMALIZED",
        })

        manifest, manifest_meta, manifest_error = safe_get_json(args.base_url, manifest_url, args.timeout)
        manifest_counts = (manifest or {}).get("artifact_counts") or {}
        manifest_match = manifest is not None and manifest.get("pack_id") == pack_id
        counts_match = manifest_counts == (sync_item.get("artifact_counts") or {})
        manifest_rows.append({
            "pack_id": pack_id,
            "status": manifest_meta.get("status"),
            "body_bytes": manifest_meta.get("body_bytes", 0),
            "error": manifest_error,
            "manifest_pack_id": (manifest or {}).get("pack_id"),
            "pack_id_matches": manifest_match,
            "artifact_counts_match": counts_match,
        })

        started = time.perf_counter()
        payload, download_meta, download_error = safe_get_bytes(args.base_url, download_url, args.timeout)
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        archive_error = None
        inventory: dict[str, Any] = {"files": [], "missing_required_files": sorted(REQUIRED_ARCHIVE_FILES), "manifest": {}, "content_count": 0}
        if payload:
            try:
                inventory = archive_inventory(payload)
            except Exception as exc:  # noqa: BLE001 - report exact archive failure
                archive_error = str(exc)
        content_length = (download_meta.get("headers") or {}).get("Content-Length") or (download_meta.get("headers") or {}).get("content-length")
        download_rows.append({
            "pack_id": pack_id,
            "status": download_meta.get("status"),
            "content_type": (download_meta.get("headers") or {}).get("Content-Type") or (download_meta.get("headers") or {}).get("content-type"),
            "content_length": content_length,
            "body_bytes": download_meta.get("body_bytes", 0),
            "duration_ms": duration_ms,
            "error": download_error,
            "archive_opens": payload is not None and archive_error is None,
            "archive_error": archive_error,
            "missing_required_files": inventory["missing_required_files"],
            "archive_content_count": inventory["content_count"],
        })

        checksum_ok = manifest is not None and checksum_match(sync_item, manifest, inventory["manifest"])
        checksum_rows.append({
            "pack_id": pack_id,
            "checksum_ok": checksum_ok,
            "sync_checksum": sync_item.get("checksum"),
            "manifest_checksum": ((manifest or {}).get("metadata") or {}).get("checksum") or (manifest or {}).get("checksum"),
            "archive_manifest_checksum": inventory["manifest"].get("checksum"),
        })

        archive_ok = (
            download_meta.get("status") == 200
            and int(download_meta.get("body_bytes") or 0) > 0
            and archive_error is None
            and not inventory["missing_required_files"]
        )
        contract_rows.append({
            "pack_id": pack_id,
            "in_packs_catalog": pack_id in packs_by_id,
            "required_fields_present": not missing_fields,
            "manifest_ok": manifest_meta.get("status") == 200 and manifest_match and counts_match,
            "download_ok": archive_ok,
            "id_ok": normalized and pack_id not in duplicate_ids and urls_encoded,
            "checksum_ok": checksum_ok,
            "installable_flag": sync_item.get("installable") is True,
            "archive_exists_flag": sync_item.get("archive_exists") is True,
            "manifest_exists_flag": sync_item.get("manifest_exists") is True,
        })

        if sample_manifest is None and manifest is not None:
            sample_manifest = manifest
        if sample_download is None and archive_ok:
            sample_download = download_rows[-1] | {
                "archive_files": inventory["files"],
                "archive_manifest_pack_id": inventory["manifest"].get("pack_id"),
                "archive_manifest_checksum": inventory["manifest"].get("checksum"),
                "archive_sha256": hashlib.sha256(payload or b"").hexdigest(),
            }

    broken_downloads = [row for row in download_rows if row["status"] != 200 or row["body_bytes"] <= 0 or not row["archive_opens"] or row["missing_required_files"]]
    broken_manifests = [row for row in manifest_rows if row["status"] != 200 or not row["pack_id_matches"] or not row["artifact_counts_match"]]
    id_mismatches = [row for row in id_rows if not row["normalized"] or row["duplicate"] or not row["urls_percent_encoded"]]
    checksum_mismatches = [row for row in checksum_rows if not row["checksum_ok"]]
    installable_rows = [
        row for row in contract_rows
        if row["required_fields_present"]
        and row["manifest_ok"]
        and row["download_ok"]
        and row["id_ok"]
        and row["checksum_ok"]
        and row["installable_flag"]
        and row["archive_exists_flag"]
        and row["manifest_exists_flag"]
    ]

    summary = {
        "total_packs": len(sync_packs),
        "catalog_packs": len(packs),
        "installable_packs": len(installable_rows),
        "broken_downloads": len(broken_downloads),
        "broken_manifests": len(broken_manifests),
        "id_mismatches": len(id_mismatches),
        "checksum_mismatches": len(checksum_mismatches),
        "missing_required_field_entries": len(missing_field_rows),
        "packs_response": packs_meta,
        "sync_response": sync_meta,
        "success_criteria_met": len(sync_packs) == 405
        and len(installable_rows) == 405
        and not broken_downloads
        and not broken_manifests
        and not id_mismatches
        and not checksum_mismatches,
    }

    output = {
        "summary": summary,
        "missing_field_rows": missing_field_rows,
        "manifest_rows": manifest_rows,
        "download_rows": download_rows,
        "id_rows": id_rows,
        "checksum_rows": checksum_rows,
        "contract_rows": contract_rows,
        "samples": {
            "sync_entry": sync_packs[:1],
            "manifest": sample_manifest,
            "download": sample_download,
        },
    }
    (output_dir / "pack_sync_production_contract_audit.json").write_text(
        json.dumps(output, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )

    field_rows = [
        ["total_packs", summary["total_packs"]],
        ["installable_packs", summary["installable_packs"]],
        ["broken_downloads", summary["broken_downloads"]],
        ["broken_manifests", summary["broken_manifests"]],
        ["id_mismatches", summary["id_mismatches"]],
        ["checksum_mismatches", summary["checksum_mismatches"]],
        ["missing_required_field_entries", summary["missing_required_field_entries"]],
    ]
    report = "\n".join([
        "# Pack Sync Production Contract Audit",
        "",
        "## Consistency Summary",
        "",
        markdown_table(["Metric", "Value"], field_rows),
        "",
        f"Success criteria met: `{summary['success_criteria_met']}`",
        "",
        "## Required Sync Fields",
        "",
        f"Required fields: `{', '.join(sorted(REQUIRED_SYNC_FIELDS))}`",
        "",
        "Missing field failures:",
        "",
        markdown_table(["pack_id", "missing_fields"], [[row["pack_id"], ",".join(row["missing_fields"])] for row in missing_field_rows[:50]]),
        "",
        "## Download Failures",
        "",
        markdown_table(["pack_id", "status", "content_length", "body_bytes", "error", "archive_error", "missing_files"], [[row["pack_id"], row["status"], row["content_length"], row["body_bytes"], row["error"], row["archive_error"], ",".join(row["missing_required_files"])] for row in broken_downloads[:50]]),
        "",
        "## Manifest Failures",
        "",
        markdown_table(["pack_id", "status", "manifest_pack_id", "pack_id_matches", "artifact_counts_match", "error"], [[row["pack_id"], row["status"], row["manifest_pack_id"], row["pack_id_matches"], row["artifact_counts_match"], row["error"]] for row in broken_manifests[:50]]),
        "",
        "## ID Normalization Failures",
        "",
        markdown_table(["pack_id", "normalized", "duplicate", "urls_percent_encoded", "manifest_url", "download_url"], [[row["pack_id"], row["normalized"], row["duplicate"], row["urls_percent_encoded"], row["manifest_url"], row["download_url"]] for row in id_mismatches[:50]]),
        "",
        "## Checksum Failures",
        "",
        markdown_table(["pack_id", "sync_checksum", "manifest_checksum", "archive_manifest_checksum"], [[row["pack_id"], row["sync_checksum"], row["manifest_checksum"], row["archive_manifest_checksum"]] for row in checksum_mismatches[:50]]),
        "",
        "## Sample Sync Entry",
        "",
        "```json",
        json.dumps(sync_packs[:1], indent=2, ensure_ascii=False),
        "```",
        "",
        "## Sample Manifest",
        "",
        "```json",
        json.dumps(sample_manifest, indent=2, ensure_ascii=False),
        "```",
        "",
        "## Sample Download Evidence",
        "",
        "```json",
        json.dumps(sample_download, indent=2, ensure_ascii=False),
        "```",
    ])
    (output_dir / "PACK_SYNC_PRODUCTION_CONTRACT_REPORT.md").write_text(report, encoding="utf-8")

    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
