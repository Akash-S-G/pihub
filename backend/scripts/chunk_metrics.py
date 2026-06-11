#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from content_quality_audit import classify_text, content_hash, length_words, normalize_text, qdrant_post, qdrant_scroll


def collection_count(qdrant_url: str, collection: str, timeout: float) -> int:
    url = f"{qdrant_url.rstrip('/')}/collections/{collection}"
    with urllib.request.urlopen(url, timeout=timeout) as response:
        data = json.loads(response.read().decode("utf-8"))
    return int(data.get("result", {}).get("points_count", 0))


def payload_text(payload: dict[str, Any]) -> str:
    value = payload.get("text")
    return value if isinstance(value, str) else ""


def percentile(values: list[int], pct: float) -> int:
    if not values:
        return 0
    values = sorted(values)
    index = min(len(values) - 1, max(0, int(round((pct / 100) * (len(values) - 1)))))
    return values[index]


def near_duplicate_key(text: str) -> str:
    words = re.findall(r"[a-z0-9]+", normalize_text(text))
    if len(words) < 12:
        return ""
    shingles = [" ".join(words[index:index + 5]) for index in range(0, max(1, len(words) - 4))]
    selected = sorted(set(shingles))[:12]
    return hashlib.sha1("|".join(selected).encode("utf-8")).hexdigest()


def markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(cell).replace("\n", " ") for cell in row) + " |")
    return "\n".join(lines)


def write_report(path: Path, report: dict[str, Any]) -> None:
    chapter_rows = [
        [
            item["subject"],
            item["chapter"],
            item["sampled_chunks"],
            item["duplicate_chunks"],
            item["duplicate_ratio"],
            item["ocr_noise_ratio"],
            item["educational_ratio"],
        ]
        for item in report["chapter_metrics"][:60]
    ]
    text = [
        "# Chunk Metrics Report",
        "",
        "## Global Metrics",
        "",
        json.dumps(report["global_metrics"], indent=2, ensure_ascii=False),
        "",
        "## Threshold Analysis",
        "",
        json.dumps(report["threshold_analysis"], indent=2, ensure_ascii=False),
        "",
        "## Duplicate Analysis",
        "",
        json.dumps(report["duplicate_analysis"], indent=2, ensure_ascii=False),
        "",
        "## OCR Noise By Chapter",
        "",
        markdown_table(
            ["subject", "chapter", "sampled", "duplicate_chunks", "duplicate_ratio", "ocr_noise_ratio", "educational_ratio"],
            chapter_rows,
        ),
    ]
    path.write_text("\n".join(text), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute PIHUB Qdrant chunk quality metrics without mutating content.")
    parser.add_argument("--qdrant-url", default="http://qdrant:6333")
    parser.add_argument("--collection", default="educational_chunks")
    parser.add_argument("--sample-chunks", type=int, default=1000)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()

    points = qdrant_scroll(args.qdrant_url, args.collection, args.sample_chunks, args.timeout)
    total_chunks = collection_count(args.qdrant_url, args.collection, args.timeout)

    seen_for_classification: set[str] = set()
    exact_hashes: Counter[str] = Counter()
    near_hashes: Counter[str] = Counter()
    lengths: list[int] = []
    word_lengths: list[int] = []
    class_counts: Counter[str] = Counter()
    chapter_groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)

    for point in points:
        payload = point.get("payload") or {}
        text = payload_text(payload)
        lengths.append(len(text))
        word_lengths.append(length_words(text))
        exact_hashes[content_hash(text)] += 1
        near_key = near_duplicate_key(text)
        if near_key:
            near_hashes[near_key] += 1
        category = classify_text(text, seen_for_classification)
        class_counts[category] += 1
        chapter_groups[(str(payload.get("subject")), str(payload.get("chapter")))].append({
            "text": text,
            "category": category,
        })

    exact_duplicate_chunks = sum(count - 1 for count in exact_hashes.values() if count > 1)
    near_duplicate_chunks = sum(count - 1 for count in near_hashes.values() if count > 1)
    sampled = len(points)

    chapter_metrics: list[dict[str, Any]] = []
    for (subject, chapter), items in chapter_groups.items():
        counts = Counter(item["category"] for item in items)
        count = len(items)
        chapter_metrics.append({
            "subject": subject,
            "chapter": chapter,
            "sampled_chunks": count,
            "duplicate_chunks": counts["DUPLICATE_CONTENT"],
            "duplicate_ratio": round(counts["DUPLICATE_CONTENT"] / count, 4) if count else 0,
            "ocr_noise_ratio": round(counts["OCR_NOISE"] / count, 4) if count else 0,
            "educational_ratio": round(counts["EDUCATIONAL_TEXT"] / count, 4) if count else 0,
            "classification_counts": dict(counts),
        })
    chapter_metrics.sort(key=lambda item: (item["ocr_noise_ratio"], item["duplicate_ratio"], -item["educational_ratio"]), reverse=True)

    report = {
        "global_metrics": {
            "total_chunks": total_chunks,
            "sampled_chunks": sampled,
            "unique_chunks_in_sample": len(exact_hashes),
            "duplicate_chunks_in_sample": exact_duplicate_chunks,
            "near_duplicate_chunks_in_sample": near_duplicate_chunks,
            "minimum_length": min(lengths) if lengths else 0,
            "maximum_length": max(lengths) if lengths else 0,
            "average_length": round(statistics.mean(lengths), 2) if lengths else 0,
            "median_length": round(statistics.median(lengths), 2) if lengths else 0,
            "p90_length": percentile(lengths, 90),
            "classification_counts": dict(class_counts),
            "educational_ratio": round(class_counts["EDUCATIONAL_TEXT"] / sampled, 4) if sampled else 0,
            "ocr_noise_ratio": round(class_counts["OCR_NOISE"] / sampled, 4) if sampled else 0,
        },
        "threshold_analysis": {
            "length_lt_10": sum(1 for value in lengths if value < 10),
            "length_lt_25": sum(1 for value in lengths if value < 25),
            "length_lt_50": sum(1 for value in lengths if value < 50),
            "length_lt_100": sum(1 for value in lengths if value < 100),
        },
        "duplicate_analysis": {
            "exact_duplicates": exact_duplicate_chunks,
            "near_duplicates": near_duplicate_chunks,
            "exact_duplicate_ratio": round(exact_duplicate_chunks / sampled, 4) if sampled else 0,
            "near_duplicate_ratio": round(near_duplicate_chunks / sampled, 4) if sampled else 0,
        },
        "chapter_metrics": chapter_metrics,
    }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "chunk_metrics.json").write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    write_report(output_dir / "CHUNK_METRICS_REPORT.md", report)
    print(json.dumps(report["global_metrics"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
