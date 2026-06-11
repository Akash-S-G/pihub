#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DAMAGED_STATUSES = {"METADATA_MISMATCH", "PARTIAL_ARCHIVE", "EMPTY_ARCHIVE"}


def load_rows(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict):
        for key in ("packs", "rows", "items", "results"):
            value = data.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
    raise ValueError(f"Unsupported integrity JSON shape: {path}")


def pack_payload(row: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "pack_type": "chapter" if row.get("chapter") else "class",
        "grade": row.get("grade"),
        "subject": row.get("subject"),
        "chapter": row.get("chapter"),
        "language": row.get("language") or "english",
    }
    return {key: value for key, value in payload.items() if value not in (None, "")}


def post_json(url: str, payload: dict[str, Any], timeout: float) -> tuple[int, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed: Any = json.loads(body)
        except json.JSONDecodeError:
            parsed = body
        return exc.code, parsed


def main() -> None:
    parser = argparse.ArgumentParser(description="Regenerate only damaged runtime packs from a pack integrity audit.")
    parser.add_argument("--input", required=True, help="pack_publication_integrity.json path")
    parser.add_argument("--output", required=True, help="JSON result path")
    parser.add_argument("--pack-service-url", default="http://localhost:8030")
    parser.add_argument("--statuses", default=",".join(sorted(DAMAGED_STATUSES)))
    parser.add_argument("--limit", type=int)
    parser.add_argument("--pack-id", action="append", default=[])
    parser.add_argument("--timeout", type=float, default=300.0)
    args = parser.parse_args()

    allowed_statuses = {item.strip() for item in args.statuses.split(",") if item.strip()}
    requested_ids = set(args.pack_id)
    rows = [
        row
        for row in load_rows(Path(args.input))
        if row.get("publication_status") in allowed_statuses
        and (not requested_ids or row.get("pack_id") in requested_ids)
    ]
    rows.sort(key=lambda row: str(row.get("pack_id") or ""))
    if args.limit is not None:
        rows = rows[: args.limit]

    results: list[dict[str, Any]] = []
    url = f"{args.pack_service_url.rstrip('/')}/packs/generate"
    started = time.time()
    for row in rows:
        payload = pack_payload(row)
        before = time.time()
        status_code, response = post_json(url, payload, args.timeout)
        duration_ms = round((time.time() - before) * 1000, 2)
        results.append(
            {
                "pack_id": row.get("pack_id"),
                "before_status": row.get("publication_status"),
                "before_qdrant_available_count": row.get("qdrant_available_count"),
                "before_qdrant_generator_count": row.get("qdrant_generator_count"),
                "before_archive_chunk_count": row.get("archive_chunk_count"),
                "before_manifest_chunk_count": row.get("manifest_chunk_count"),
                "payload": payload,
                "status_code": status_code,
                "response": response,
                "duration_ms": duration_ms,
            }
        )

    summary = {
        "requested": len(rows),
        "succeeded": sum(1 for item in results if 200 <= int(item["status_code"]) < 300),
        "failed": sum(1 for item in results if int(item["status_code"]) >= 300),
        "duration_ms": round((time.time() - started) * 1000, 2),
    }
    output = {"summary": summary, "results": results}
    Path(args.output).write_text(json.dumps(output, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
