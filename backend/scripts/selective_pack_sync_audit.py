#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
import tarfile
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from io import BytesIO
from pathlib import Path
from typing import Any


def get_bytes(base_url: str, path: str, timeout: float) -> tuple[bytes, dict[str, Any]]:
    started = time.perf_counter()
    with urllib.request.urlopen(f"{base_url.rstrip('/')}{path}", timeout=timeout) as response:
        body = response.read()
        return body, {
            "status": response.status,
            "headers": dict(response.headers),
            "body_bytes": len(body),
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        }


def get_json(base_url: str, path: str, timeout: float) -> tuple[dict[str, Any], dict[str, Any]]:
    body, meta = get_bytes(base_url, path, timeout)
    return json.loads(body.decode("utf-8")), meta


def query_path(path: str, params: dict[str, Any]) -> str:
    clean = {key: value for key, value in params.items() if value is not None}
    if not clean:
        return path
    return f"{path}?{urllib.parse.urlencode(clean)}"


def archive_ok(payload: bytes) -> bool:
    with tarfile.open(fileobj=BytesIO(payload), mode="r:gz") as archive:
        files = {member.name.split("/", 1)[-1] for member in archive.getmembers() if member.isfile()}
    return {"manifest.json", "content.json", "quizzes.json", "summaries.json", "glossary.json"}.issubset(files)


def markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(cell).replace("\n", " ") for cell in row) + " |")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate PIHUB selective pack sync contract.")
    parser.add_argument("--base-url", default="http://localhost")
    parser.add_argument("--output-dir", default=".")
    parser.add_argument("--timeout", type=float, default=90.0)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    unfiltered, unfiltered_meta = get_json(args.base_url, "/packs/sync", args.timeout)
    packs = unfiltered.get("packs", [])
    first_grade = next((pack.get("grade") for pack in packs if pack.get("grade") is not None), None)
    first_subject = next((pack.get("subject") for pack in packs if pack.get("subject")), None)
    first_language = next((pack.get("language") for pack in packs if pack.get("language")), None)

    filter_specs = [
        ("all", {}),
        ("grade", {"grade": first_grade}),
        ("subject", {"subject": first_subject}),
        ("language", {"language": first_language}),
        ("grade_subject", {"grade": first_grade, "subject": first_subject}),
    ]
    filter_results: list[dict[str, Any]] = []
    for name, params in filter_specs:
        path = query_path("/packs/sync", params)
        body, meta = get_json(args.base_url, path, args.timeout)
        filter_results.append({
            "name": name,
            "path": path,
            "count": body.get("count", len(body.get("packs", []))),
            "packs_len": len(body.get("packs", [])),
            "latency_ms": meta["latency_ms"],
            "body_bytes": meta["body_bytes"],
            "filters": body.get("filters", {}),
            "contract_fields_ok": all(
                all(field in pack for field in ("pack_id", "version", "checksum", "size_bytes", "manifest_url", "download_url", "artifact_counts", "chunk_count", "installable"))
                for pack in body.get("packs", [])
            ),
        })

    catalog, catalog_meta = get_json(args.base_url, "/packs/catalog", args.timeout)
    recommended_path = query_path("/packs/recommended", {"grade": first_grade, "subject": first_subject, "installed_pack_ids": ""})
    recommended, recommended_meta = get_json(args.base_url, recommended_path, args.timeout)

    grade_totals: dict[int, dict[str, Any]] = defaultdict(lambda: {"pack_count": 0, "chunk_count": 0, "download_size_bytes": 0})
    for pack in packs:
        try:
            grade = int(pack.get("grade"))
        except (TypeError, ValueError):
            continue
        grade_totals[grade]["pack_count"] += 1
        grade_totals[grade]["chunk_count"] += int((pack.get("artifact_counts") or {}).get("content") or 0)
        grade_totals[grade]["download_size_bytes"] += int(pack.get("size_bytes") or 0)
    grade_rows = [
        [grade, values["pack_count"], values["chunk_count"], round(values["download_size_bytes"] / (1024 * 1024), 2)]
        for grade, values in sorted(grade_totals.items())
    ]

    validation_rows: list[dict[str, Any]] = []
    for pack in packs[:5]:
        manifest, manifest_meta = get_json(args.base_url, str(pack["manifest_url"]), args.timeout)
        archive_payload, download_meta = get_bytes(args.base_url, str(pack["download_url"]), args.timeout)
        validation_rows.append({
            "pack_id": pack["pack_id"],
            "manifest_status": manifest_meta["status"],
            "manifest_pack_id_matches": manifest.get("pack_id") == pack["pack_id"],
            "manifest_counts_match": manifest.get("artifact_counts") == pack.get("artifact_counts"),
            "download_status": download_meta["status"],
            "download_content_length": download_meta["headers"].get("Content-Length") or download_meta["headers"].get("content-length"),
            "archive_ok": archive_ok(archive_payload),
        })

    latencies = [row["latency_ms"] for row in filter_results] + [catalog_meta["latency_ms"], recommended_meta["latency_ms"]]
    summary = {
        "total_packs": len(packs),
        "average_pack_size_bytes": round(statistics.mean(int(pack.get("size_bytes") or 0) for pack in packs), 2) if packs else 0,
        "average_pack_size_mb": round(statistics.mean(int(pack.get("size_bytes") or 0) for pack in packs) / (1024 * 1024), 2) if packs else 0,
        "filtering_performance_ms": {
            "average": round(statistics.mean(latencies), 2),
            "max": round(max(latencies), 2),
            "min": round(min(latencies), 2),
        },
        "unfiltered_count": unfiltered.get("count", len(packs)),
        "catalog_grade_count": len(catalog.get("grades", [])),
        "recommended_count": recommended.get("count"),
        "contract_regressions": sum(1 for row in filter_results if not row["contract_fields_ok"]),
        "manifest_validation_failures": sum(1 for row in validation_rows if not row["manifest_pack_id_matches"] or not row["manifest_counts_match"]),
        "download_validation_failures": sum(1 for row in validation_rows if row["download_status"] != 200 or not row["archive_ok"]),
    }
    output = {
        "summary": summary,
        "filter_results": filter_results,
        "catalog": catalog,
        "catalog_meta": catalog_meta,
        "recommended": recommended,
        "recommended_meta": recommended_meta,
        "grade_rows": grade_rows,
        "validation_rows": validation_rows,
    }
    output_dir.joinpath("selective_pack_sync_audit.json").write_text(
        json.dumps(output, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )

    report = "\n".join([
        "# Selective Pack Sync Audit",
        "",
        "## Summary",
        "",
        "```json",
        json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True),
        "```",
        "",
        "## Packs Per Grade",
        "",
        markdown_table(["Grade", "Packs", "Chunks", "Download size MB"], grade_rows),
        "",
        "## Filtering Performance",
        "",
        markdown_table(["Name", "Path", "Count", "Latency ms", "Body bytes", "Contract fields OK"], [[row["name"], row["path"], row["count"], row["latency_ms"], row["body_bytes"], row["contract_fields_ok"]] for row in filter_results]),
        "",
        "## Catalog Endpoint",
        "",
        f"Latency ms: {catalog_meta['latency_ms']}",
        f"Grades returned: {len(catalog.get('grades', []))}",
        "",
        "## Recommended Endpoint",
        "",
        f"Path: `{recommended_path}`",
        f"Latency ms: {recommended_meta['latency_ms']}",
        f"Recommended count: {recommended.get('count')}",
        "",
        "## Manifest And Download Validation",
        "",
        markdown_table(["pack_id", "manifest_status", "manifest_id_match", "counts_match", "download_status", "content_length", "archive_ok"], [[row["pack_id"], row["manifest_status"], row["manifest_pack_id_matches"], row["manifest_counts_match"], row["download_status"], row["download_content_length"], row["archive_ok"]] for row in validation_rows]),
        "",
        "## Verification",
        "",
        f"Existing `/packs/sync` works: `{summary['unfiltered_count'] == summary['total_packs']}`",
        f"Filtered sync works: `{all(row['packs_len'] == row['count'] for row in filter_results)}`",
        f"No pack contract regressions: `{summary['contract_regressions'] == 0}`",
        f"Manifest URLs still valid: `{summary['manifest_validation_failures'] == 0}`",
        f"Download URLs still valid: `{summary['download_validation_failures'] == 0}`",
    ])
    output_dir.joinpath("SELECTIVE_PACK_SYNC_AUDIT_REPORT.md").write_text(report, encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
