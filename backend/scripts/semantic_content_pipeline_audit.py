#!/usr/bin/env python3
from __future__ import annotations

import argparse
import io
import json
import tarfile
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pack-service"))

from app.semantic_content_pipeline import SemanticContentPipeline  # noqa: E402


def fetch_json(url: str, timeout: float) -> Any:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_bytes(url: str, timeout: float) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.read()


def archive_json(payload: bytes, suffix: str) -> Any:
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
        for member in archive.getmembers():
            if member.name.endswith(suffix):
                file_obj = archive.extractfile(member)
                if file_obj is None:
                    return None
                return json.loads(file_obj.read().decode("utf-8"))
    return None


def sync_packs(base_url: str, timeout: float) -> list[dict[str, Any]]:
    data = fetch_json(f"{base_url.rstrip('/')}/packs/sync", timeout)
    packs = data.get("packs", data if isinstance(data, list) else [])
    return [pack for pack in packs if isinstance(pack, dict)]


def select_samples(packs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    targets = [("8", "science"), ("8", "maths")]
    for grade, subject in targets:
        match = next(
            (
                pack
                for pack in packs
                if str(pack.get("grade")) == grade
                and str(pack.get("subject") or "").lower() in {subject, "mathematics" if subject == "maths" else subject}
                and pack.get("download_url")
            ),
            None,
        )
        if match:
            samples.append(match)
    return samples


def report_markdown(
    before: dict[str, Any],
    after_rows: list[dict[str, Any]],
    sample_dirs: list[str],
    elapsed_ms: float,
) -> str:
    averages = {
        "after_average_chunk_length": round(sum(row["after"]["chunk_quality"]["average_chunk_length"] for row in after_rows) / max(1, len(after_rows)), 2),
        "after_duplicate_ratio": round(sum(row["after"]["quality_gate"]["metrics"]["duplicate_ratio"] for row in after_rows) / max(1, len(after_rows)), 4),
        "after_retrieval_precision": round(sum(float(row["after"]["rag_validation"]["retrieval_precision"]) for row in after_rows) / max(1, len(after_rows)), 4),
        "quality_gate_passed": sum(1 for row in after_rows if row["after"]["quality_gate"]["passed"]),
    }
    lines = [
        "# Semantic Content Pipeline Validation",
        "",
        "## Scope",
        "",
        "FACT: This report runs the new semantic educational knowledge pipeline against sampled runtime pack archives through the backend pack contract.",
        "FACT: It does not mutate Qdrant, the frontend, discovery, marketplace, voice, or experiment engine.",
        "",
        "## Before Metrics",
        "",
        "```json",
        json.dumps(before, indent=2, sort_keys=True),
        "```",
        "",
        "## After Sample Metrics",
        "",
        "```json",
        json.dumps(averages, indent=2, sort_keys=True),
        "```",
        "",
        "## Sample Regenerated Packs",
        "",
        *[f"- {path}" for path in sample_dirs],
        "",
        "## Pack Rows",
        "",
        "```json",
        json.dumps(after_rows, indent=2, ensure_ascii=False, sort_keys=True),
        "```",
        "",
        "## Runtime",
        "",
        f"duration_ms: {elapsed_ms}",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate semantic pack content pipeline against runtime packs.")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--output-dir", default=".")
    parser.add_argument("--timeout", type=float, default=90.0)
    args = parser.parse_args()

    started = time.time()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    sample_root = output_dir / "semantic_pack_samples"
    sample_root.mkdir(parents=True, exist_ok=True)

    previous_audit = output_dir / "content_extraction_audit.json"
    before = {}
    if previous_audit.exists():
        previous = json.loads(previous_audit.read_text(encoding="utf-8"))
        before = previous.get("summary", {})

    packs = sync_packs(args.base_url, args.timeout)
    samples = select_samples(packs)
    pipeline = SemanticContentPipeline()
    rows: list[dict[str, Any]] = []
    sample_dirs: list[str] = []

    for pack in samples:
        download_url = urllib.parse.urljoin(args.base_url.rstrip("/") + "/", str(pack["download_url"]).lstrip("/"))
        payload = fetch_bytes(download_url, args.timeout)
        content = archive_json(payload, "/content.json") or []
        result = pipeline.build(content, pack_id=str(pack["pack_id"]), metadata=pack)
        sample_dir = sample_root / str(pack["pack_id"])
        sample_dir.mkdir(parents=True, exist_ok=True)
        for filename, value in {
            "content.json": result.artifacts["content"],
            "concepts.json": result.artifacts["concepts"],
            "examples.json": result.artifacts["examples"],
            "worked_examples.json": result.artifacts["worked_examples"],
            "activities.json": result.artifacts["activities"],
            "questions.json": result.artifacts["questions"],
            "glossary.json": result.artifacts["glossary"],
            "summaries.json": result.artifacts["summaries"],
            "chunk_quality_report.json": result.reports["chunk_quality"],
            "rag_validation_report.json": result.reports["rag_validation"],
            "quality_gate.json": result.quality_gate,
        }.items():
            (sample_dir / filename).write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        sample_dirs.append(str(sample_dir))
        rows.append(
            {
                "pack_id": pack.get("pack_id"),
                "grade": pack.get("grade"),
                "subject": pack.get("subject"),
                "chapter": pack.get("chapter"),
                "before": {"content_chunks": len(content), "size_bytes": pack.get("size_bytes")},
                "after": {
                    "content_classification": result.reports["content_classification"],
                    "content_cleanup": result.reports["content_cleanup"],
                    "deduplication": result.reports["deduplication"],
                    "chunk_quality": result.reports["chunk_quality"],
                    "rag_validation": result.reports["rag_validation"],
                    "quality_gate": result.quality_gate,
                },
            }
        )

    aggregate_reports = {
        "content_classification": rows,
        "content_cleanup": rows,
        "deduplication": rows,
        "chunk_quality": rows,
        "rag_validation": rows,
    }
    (output_dir / "content_classification.json").write_text(json.dumps(aggregate_reports["content_classification"], indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    (output_dir / "content_cleanup_report.json").write_text(json.dumps(aggregate_reports["content_cleanup"], indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    (output_dir / "deduplication_report.json").write_text(json.dumps(aggregate_reports["deduplication"], indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    (output_dir / "chunk_quality_report.json").write_text(json.dumps(aggregate_reports["chunk_quality"], indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    (output_dir / "rag_validation_report.json").write_text(json.dumps(aggregate_reports["rag_validation"], indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    (output_dir / "SEMANTIC_CONTENT_PIPELINE_VALIDATION.md").write_text(
        report_markdown(before, rows, sample_dirs, round((time.time() - started) * 1000, 2)),
        encoding="utf-8",
    )
    print(json.dumps({"samples": len(rows), "sample_dirs": sample_dirs}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
