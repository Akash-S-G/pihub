#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_REGISTRY = Path(__file__).resolve().parents[1] / "curriculum-builder" / "complete_build" / "pack_registry.json"


def _load_registry(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    packs = data.get("packs", {})
    if isinstance(packs, dict):
        return [value for value in packs.values() if isinstance(value, dict)]
    if isinstance(packs, list):
        return [value for value in packs if isinstance(value, dict)]
    raise ValueError(f"Unsupported pack registry shape: {path}")


def _payload_from_registry_record(record: dict[str, Any]) -> dict[str, Any] | None:
    grade = record.get("grade")
    subject = record.get("subject")
    chapter = record.get("chapter")
    language = record.get("language") or "english"

    if grade is not None and subject and chapter:
        return {
            "pack_type": "chapter",
            "grade": int(grade),
            "subject": subject,
            "chapter": chapter,
            "language": language,
        }

    if grade is not None and subject:
        return {
            "pack_type": "class",
            "grade": int(grade),
            "subject": subject,
            "language": language,
        }

    if language:
        return {
            "pack_type": "language",
            "language": language,
            "grade": int(grade) if grade is not None else None,
            "subject": subject,
        }

    return None


def _post_json(url: str, payload: dict[str, Any], timeout: float) -> tuple[int, dict[str, Any] | str]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, method="POST")
    request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            text = response.read().decode("utf-8")
            try:
                return response.status, json.loads(text)
            except json.JSONDecodeError:
                return response.status, text
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(text)
        except json.JSONDecodeError:
            return exc.code, text


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Materialize curriculum-builder pack metadata into runtime pack-service storage "
            "by calling the existing POST /packs/generate endpoint."
        )
    )
    parser.add_argument("--registry-path", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--pack-service-url", default="http://localhost:8030")
    parser.add_argument("--limit", type=int, default=0, help="Maximum records to process. 0 means all.")
    parser.add_argument("--sleep", type=float, default=0.05)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--execute", action="store_true", help="Actually call pack-service. Without this, print dry-run payloads.")
    args = parser.parse_args()

    records = _load_registry(Path(args.registry_path))
    selected = records[: args.limit] if args.limit and args.limit > 0 else records
    generate_url = f"{args.pack_service_url.rstrip('/')}/packs/generate"
    summary: dict[str, Any] = {
        "registry_path": args.registry_path,
        "pack_service_url": args.pack_service_url,
        "total_registry_records": len(records),
        "selected_records": len(selected),
        "execute": args.execute,
        "generated": 0,
        "skipped": 0,
        "failed": 0,
        "results": [],
    }

    seen_payloads: set[str] = set()
    for record in selected:
        payload = _payload_from_registry_record(record)
        if payload is None:
            summary["skipped"] += 1
            summary["results"].append({"pack_id": record.get("pack_id"), "status": "skipped", "reason": "insufficient metadata"})
            continue

        payload_key = json.dumps(payload, sort_keys=True)
        if payload_key in seen_payloads:
            summary["skipped"] += 1
            summary["results"].append({"pack_id": record.get("pack_id"), "status": "skipped", "reason": "duplicate generation payload", "payload": payload})
            continue
        seen_payloads.add(payload_key)

        if not args.execute:
            summary["results"].append({"pack_id": record.get("pack_id"), "status": "dry_run", "payload": payload})
            continue

        try:
            status, response = _post_json(generate_url, payload, args.timeout)
        except OSError as exc:
            summary["failed"] += 1
            summary["results"].append({"pack_id": record.get("pack_id"), "status": "failed", "error": str(exc), "payload": payload})
            continue

        if 200 <= status < 300:
            summary["generated"] += 1
            summary["results"].append({"pack_id": record.get("pack_id"), "status": "generated", "http_status": status, "payload": payload, "response": response})
        else:
            summary["failed"] += 1
            summary["results"].append({"pack_id": record.get("pack_id"), "status": "failed", "http_status": status, "payload": payload, "response": response})
        time.sleep(args.sleep)

    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
