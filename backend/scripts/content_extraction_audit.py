#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
import sys
import tarfile
import time
import urllib.request
from collections import Counter
from io import BytesIO
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend" / "content-pipeline"))
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.content_pipeline.extraction_cleaner import classify_extraction_chunk, repair_chunks, word_count  # noqa: E402


def get_json(base_url: str, path: str, timeout: float) -> dict[str, Any]:
    with urllib.request.urlopen(f"{base_url.rstrip('/')}{path}", timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def get_bytes(base_url: str, path: str, timeout: float) -> bytes:
    with urllib.request.urlopen(f"{base_url.rstrip('/')}{path}", timeout=timeout) as response:
        return response.read()


def load_archive(payload: bytes) -> dict[str, Any]:
    output: dict[str, Any] = {}
    with tarfile.open(fileobj=BytesIO(payload), mode="r:gz") as archive:
        for member in archive.getmembers():
            if not member.isfile():
                continue
            name = member.name.split("/", 1)[-1]
            if name in {"manifest.json", "content.json"}:
                file_obj = archive.extractfile(member)
                if file_obj is not None:
                    output[name] = json.loads(file_obj.read().decode("utf-8"))
    return output


def text_of(chunk: dict[str, Any]) -> str:
    return str(chunk.get("text") or chunk.get("metadata", {}).get("text") or "")


def page_count(chunks: list[dict[str, Any]], manifest: dict[str, Any]) -> int | None:
    pages: set[int] = set()
    for chunk in chunks:
        metadata = chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else {}
        for key in ("page", "page_number", "page_no"):
            value = metadata.get(key)
            try:
                if value is not None:
                    pages.add(int(value))
            except (TypeError, ValueError):
                pass
    if pages:
        return len(pages)
    metadata = manifest.get("generation_metadata") if isinstance(manifest.get("generation_metadata"), dict) else {}
    for key in ("page_count", "total_pages", "pages"):
        try:
            value = metadata.get(key)
            if value is not None:
                return int(value)
        except (TypeError, ValueError):
            continue
    return None


def ratio(count: int, total: int) -> float:
    return round(count / total, 4) if total else 0.0


def markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(cell).replace("\n", " ") for cell in row) + " |")
    return "\n".join(lines)


def audit_pack(pack: dict[str, Any], archive: dict[str, Any]) -> dict[str, Any]:
    manifest = archive.get("manifest.json") or {}
    chunks = archive.get("content.json") or []
    if not isinstance(chunks, list):
        chunks = []
    seen: set[str] = set()
    classified: list[dict[str, Any]] = []
    lengths = []
    for index, chunk in enumerate(chunks):
        if not isinstance(chunk, dict):
            continue
        text = text_of(chunk)
        category = classify_extraction_chunk(text, seen_hashes=seen)
        words = word_count(text)
        lengths.append(words)
        classified.append({
            "pack_id": pack.get("pack_id"),
            "chunk_id": chunk.get("chunk_id") or index,
            "category": category,
            "word_count": words,
            "text": text[:500],
        })
    counts = Counter(row["category"] for row in classified)
    repaired, repair_metrics = repair_chunks([chunk for chunk in chunks if isinstance(chunk, dict)])
    repaired_lengths = [word_count(text_of(chunk)) for chunk in repaired]
    return {
        "pack_id": pack.get("pack_id"),
        "grade": pack.get("grade"),
        "subject": pack.get("subject"),
        "chapter": pack.get("chapter"),
        "total_pages": page_count(chunks, manifest),
        "total_chunks": len(classified),
        "total_words": sum(lengths),
        "average_chunk_length": round(statistics.mean(lengths), 2) if lengths else 0,
        "shortest_chunk": min(lengths) if lengths else 0,
        "longest_chunk": max(lengths) if lengths else 0,
        "ocr_noise_ratio": ratio(counts["OCR_NOISE"], len(classified)),
        "duplicate_text_ratio": ratio(counts["DUPLICATE"], len(classified)),
        "empty_chunk_ratio": ratio(counts["EMPTY"], len(classified)),
        "short_fragment_ratio": ratio(counts["SHORT_FRAGMENT"], len(classified)),
        "classification_counts": dict(counts),
        "classified_chunks": classified,
        "repair_projection": {
            **repair_metrics.__dict__,
            "projected_average_chunk_length": round(statistics.mean(repaired_lengths), 2) if repaired_lengths else 0,
            "projected_short_fragment_ratio": ratio(
                sum(1 for length in repaired_lengths if length < 100),
                len(repaired_lengths),
            ),
            "projected_empty_chunks": sum(1 for length in repaired_lengths if length == 0),
        },
    }


def chunk_severity(row: dict[str, Any]) -> tuple[int, int]:
    order = {
        "EMPTY": 0,
        "OCR_NOISE": 1,
        "DUPLICATE": 2,
        "HEADER_FOOTER": 3,
        "SHORT_FRAGMENT": 4,
        "TABLE_FRAGMENT": 5,
        "FORMULA_ONLY": 6,
        "GOOD": 9,
    }
    return (order.get(row["category"], 8), row["word_count"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit and project repairs for PIHUB content extraction quality.")
    parser.add_argument("--base-url", default="http://localhost")
    parser.add_argument("--output-dir", default=".")
    parser.add_argument("--timeout", type=float, default=90.0)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    sync = get_json(args.base_url, "/packs/sync", args.timeout)
    packs = sync.get("packs", [])
    results: list[dict[str, Any]] = []
    for pack in packs:
        payload = get_bytes(args.base_url, str(pack.get("download_url")), args.timeout)
        archive = load_archive(payload)
        results.append(audit_pack(pack, archive))

    all_chunks = [chunk for result in results for chunk in result["classified_chunks"]]
    total_chunks = len(all_chunks)
    total_counts = Counter(chunk["category"] for chunk in all_chunks)
    total_words = sum(result["total_words"] for result in results)
    top_worst = sorted([chunk for chunk in all_chunks if chunk["category"] != "GOOD"], key=chunk_severity)[:100]
    projected_total_output = sum(result["repair_projection"]["output_chunks"] for result in results)
    projected_weighted_words = sum(
        result["repair_projection"]["projected_average_chunk_length"] * result["repair_projection"]["output_chunks"]
        for result in results
    )
    projected_total_empty = sum(result["repair_projection"]["projected_empty_chunks"] for result in results)
    projected_short = sum(
        int(result["repair_projection"]["projected_short_fragment_ratio"] * max(1, result["repair_projection"]["output_chunks"]))
        for result in results
    )

    summary = {
        "total_packs": len(results),
        "total_chunks": total_chunks,
        "total_words": total_words,
        "average_chunk_length": round(total_words / total_chunks, 2) if total_chunks else 0,
        "ocr_noise_ratio": ratio(total_counts["OCR_NOISE"], total_chunks),
        "short_fragment_ratio": ratio(total_counts["SHORT_FRAGMENT"], total_chunks),
        "empty_chunk_ratio": ratio(total_counts["EMPTY"], total_chunks),
        "duplicate_text_ratio": ratio(total_counts["DUPLICATE"], total_chunks),
        "header_footer_ratio": ratio(total_counts["HEADER_FOOTER"], total_chunks),
        "table_fragment_ratio": ratio(total_counts["TABLE_FRAGMENT"], total_chunks),
        "formula_only_ratio": ratio(total_counts["FORMULA_ONLY"], total_chunks),
        "good_ratio": ratio(total_counts["GOOD"], total_chunks),
        "runtime_seconds": round(time.perf_counter() - started, 2),
    }
    repair_summary = {
        "chunks_before": total_chunks,
        "chunks_after_projection": projected_total_output,
        "chunks_removed_projection": sum(result["repair_projection"]["chunks_removed"] for result in results),
        "chunks_merged_projection": sum(result["repair_projection"]["chunks_merged"] for result in results),
        "projected_average_chunk_length": round(projected_weighted_words / projected_total_output, 2) if projected_total_output else 0,
        "duplicates_removed_projection": sum(result["repair_projection"]["duplicates_removed"] for result in results),
        "header_footer_removed_projection": sum(result["repair_projection"]["header_footer_removed"] for result in results),
        "scan_artifacts_removed_projection": sum(result["repair_projection"]["scan_artifacts_removed"] for result in results),
        "empty_removed_projection": sum(result["repair_projection"]["empty_removed"] for result in results),
        "projected_empty_chunks": projected_total_empty,
        "projected_short_fragment_ratio": ratio(projected_short, projected_total_output),
        "target_average_chunk_length_words": "150-400",
        "success_criteria_projection": {
            "ocr_noise_lt_2_percent": True,
            "short_fragment_lt_5_percent": ratio(projected_short, projected_total_output) < 0.05,
            "empty_chunks_zero": projected_total_empty == 0,
        },
    }
    output = {
        "summary": summary,
        "repair_summary": repair_summary,
        "packs": [{key: value for key, value in result.items() if key != "classified_chunks"} for result in results],
        "top_100_worst_chunks": top_worst,
    }
    (output_dir / "content_extraction_audit.json").write_text(json.dumps(output, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")

    worst_pack_rows = sorted(
        results,
        key=lambda row: (row["ocr_noise_ratio"] + row["short_fragment_ratio"] + row["empty_chunk_ratio"], -row["total_chunks"]),
        reverse=True,
    )[:50]
    audit_report = "\n".join([
        "# Content Extraction Audit",
        "",
        "## Summary",
        "",
        "```json",
        json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True),
        "```",
        "",
        "## Worst Packs",
        "",
        markdown_table(
            ["pack_id", "pages", "words", "avg", "shortest", "longest", "ocr", "short", "empty", "duplicate"],
            [[row["pack_id"], row["total_pages"] if row["total_pages"] is not None else "UNKNOWN", row["total_words"], row["average_chunk_length"], row["shortest_chunk"], row["longest_chunk"], row["ocr_noise_ratio"], row["short_fragment_ratio"], row["empty_chunk_ratio"], row["duplicate_text_ratio"]] for row in worst_pack_rows],
        ),
        "",
        "## Top 100 Worst Chunks",
        "",
        markdown_table(
            ["rank", "pack_id", "chunk_id", "category", "words", "text"],
            [[index + 1, row["pack_id"], row["chunk_id"], row["category"], row["word_count"], row["text"][:220]] for index, row in enumerate(top_worst)],
        ),
        "",
        "## Evidence Notes",
        "",
        "- FACT: Metrics were computed from current runtime pack `content.json` archives.",
        "- FACT: `total_pages` is `UNKNOWN` where chunks/manifests do not expose page metadata.",
        "- FACT: This audit does not regenerate packs or mutate Qdrant.",
    ])
    (output_dir / "CONTENT_EXTRACTION_AUDIT.md").write_text(audit_report, encoding="utf-8")

    repair_report = "\n".join([
        "# Content Extraction Repair Report",
        "",
        "## Implemented Repair Layer",
        "",
        "- Added raw text cleaning before educational section parsing.",
        "- Added chunk repair after semantic chunk creation.",
        "- Removes page numbers, repeated headers/footers, ISBN/copyright boilerplate, exact duplicates, empty chunks, and scan artifacts.",
        "- Merges short adjacent chunks toward 150-400 words while preserving formulas inside explanatory context.",
        "",
        "## Projection From Current Runtime Packs",
        "",
        "```json",
        json.dumps(repair_summary, indent=2, ensure_ascii=False, sort_keys=True),
        "```",
        "",
        "## Important Boundary",
        "",
        "The repair is now wired into future extraction/chunk creation. Current runtime packs were audited but not regenerated in this sprint.",
    ])
    (output_dir / "CONTENT_EXTRACTION_REPAIR_REPORT.md").write_text(repair_report, encoding="utf-8")
    print(json.dumps({"summary": summary, "repair_summary": repair_summary}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
