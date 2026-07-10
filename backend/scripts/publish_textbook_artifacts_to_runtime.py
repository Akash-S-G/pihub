#!/usr/bin/env python3
"""Publish local textbook artifact chapters into the running pack-service.

This script does not read Docker internals. It speaks HTTP to the running
gateway/pack-service and re-generates the corresponding runtime pack records
for each chapter visible in `textbook_artifacts`.

The intent is to make the live containers ingest the refreshed chapter set
after a backfill or Kaggle resume recovery.
"""

from __future__ import annotations

import argparse
import json
import time
import subprocess
from pathlib import Path
from typing import Any


EXPECTED_ARTIFACTS = {
    "summary.json",
    "key_points.json",
    "concepts.json",
    "glossary.json",
    "misconceptions.json",
    "applications.json",
    "flashcards.json",
    "quizzes.json",
    "chapter_notes.json",
}

EXCLUDED_RUNTIME_CHAPTERS = {"introduction", "answers"}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def post_json(url: str, payload: dict[str, Any], timeout: float) -> tuple[int, Any]:
    command = [
        "curl",
        "-sS",
        "-m",
        str(int(timeout)),
        "-X",
        "POST",
        url,
        "-H",
        "Content-Type: application/json",
        "-d",
        json.dumps(payload),
        "-w",
        "\n%{http_code}",
    ]
    completed = subprocess.run(command, capture_output=True, text=True)
    stdout = completed.stdout.rstrip("\n")
    stderr = completed.stderr.strip()
    body, _, status_text = stdout.rpartition("\n")
    if not status_text.isdigit():
        body = stdout
        status_text = "000"
    text = body or stderr
    try:
        response = json.loads(body) if body else {}
    except json.JSONDecodeError:
        response = text
    status = int(status_text) if status_text.isdigit() else 0
    if completed.returncode != 0 and status == 0:
        status = completed.returncode
    return status, response


def discover_chapters(root: Path, min_grade: int, max_grade: int) -> list[Path]:
    chapter_roots: list[Path] = []
    for source_path in sorted(root.rglob("source/chapter_source.json")):
        chapter_root = source_path.parent.parent
        try:
            source = load_json(source_path)
        except Exception:
            continue
        if is_excluded_runtime_chapter(source):
            continue
        grade = source.get("grade")
        try:
            grade_int = int(grade)
        except Exception:
            continue
        if grade_int < min_grade or grade_int > max_grade:
            continue
        chapter_roots.append(chapter_root)
    return chapter_roots


def artifact_coverage(chapter_root: Path) -> dict[str, Any]:
    artifacts_dir = chapter_root / "artifacts"
    present = {path.name for path in artifacts_dir.glob("*.json")}
    missing = sorted(EXPECTED_ARTIFACTS - present)
    return {"present": len(present), "missing": missing}


def is_excluded_runtime_chapter(source: dict[str, Any]) -> bool:
    chapter_slug = str(source.get("chapter_slug") or source.get("chapter_title") or "").strip().lower()
    return chapter_slug in EXCLUDED_RUNTIME_CHAPTERS


def publish_chapter(
    pack_service_url: str,
    source: dict[str, Any],
    timeout: float,
) -> tuple[int, Any]:
    payload = {
        "pack_type": "chapter",
        "grade": int(source["grade"]),
        "subject": str(source["subject"]),
        "chapter": str(source.get("chapter_slug") or source.get("chapter_title") or ""),
        "language": "english",
        "include_media": False,
        "compression": "gzip",
        "quantize_embeddings": False,
    }
    return post_json(f"{pack_service_url.rstrip('/')}/packs/generate", payload, timeout=timeout)


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish textbook_artifacts chapters into the running pack-service.")
    parser.add_argument("--root", default="textbook_artifacts", help="textbook_artifacts root")
    parser.add_argument("--pack-service-url", default="http://127.0.0.1:80", help="Public gateway URL")
    parser.add_argument("--min-grade", type=int, default=6)
    parser.add_argument("--max-grade", type=int, default=10)
    parser.add_argument("--limit", type=int, default=0, help="Optional chapter limit")
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--sleep", type=float, default=0.0)
    parser.add_argument("--sync-manifest", action="store_true", help="Call /sync/manifest after publishing")
    args = parser.parse_args()

    root = Path(args.root)
    chapters = discover_chapters(root, args.min_grade, args.max_grade)
    if args.limit and args.limit > 0:
        chapters = chapters[: args.limit]

    summary: dict[str, Any] = {
        "root": str(root),
        "pack_service_url": args.pack_service_url,
        "chapters_selected": len(chapters),
        "published": 0,
        "failed": 0,
        "skipped": 0,
        "results": [],
    }

    for chapter_root in chapters:
        source_path = chapter_root / "source" / "chapter_source.json"
        try:
            source = load_json(source_path)
        except Exception as exc:
            summary["failed"] += 1
            summary["results"].append({"chapter_root": str(chapter_root), "status": "failed", "error": str(exc)})
            continue

        coverage = artifact_coverage(chapter_root)
        if coverage["missing"]:
            summary["skipped"] += 1
            summary["results"].append(
                {
                    "chapter_root": str(chapter_root),
                    "status": "skipped",
                    "reason": "missing artifacts",
                    "missing": coverage["missing"],
                }
            )
            continue

        status, response = publish_chapter(args.pack_service_url, source, timeout=args.timeout)
        if 200 <= status < 300:
            summary["published"] += 1
            summary["results"].append(
                {
                    "chapter_root": str(chapter_root),
                    "status": "published",
                    "http_status": status,
                    "response": response,
                }
            )
        else:
            summary["failed"] += 1
            summary["results"].append(
                {
                    "chapter_root": str(chapter_root),
                    "status": "failed",
                    "http_status": status,
                    "response": response,
                }
            )

        if args.sleep > 0:
            time.sleep(args.sleep)

    if args.sync_manifest:
        status, response = post_json(f"{args.pack_service_url.rstrip('/')}/sync/manifest", {}, timeout=args.timeout)
        summary["sync_manifest"] = {"http_status": status, "response": response}

    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
