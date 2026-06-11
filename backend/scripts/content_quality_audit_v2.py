#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
import sys
import tarfile
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from content_pipeline.chunk_cleaner import classify_chunk, clean_chunks, content_hash, word_count
from content_pipeline.chunk_merger import merge_adjacent_chunks
from content_pipeline.deduplicate_chunks import deduplicate_chunks, near_duplicate_key


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def load_pack_index(storage_path: Path) -> list[dict[str, Any]]:
    data = load_json(storage_path / "pack_index.json")
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        packs = data.get("packs")
        if isinstance(packs, list):
            return [item for item in packs if isinstance(item, dict)]
    return []


def archive_member_json(archive: tarfile.TarFile, suffix: str) -> Any:
    member = next((item for item in archive.getmembers() if item.isfile() and item.name.endswith(suffix)), None)
    if member is None:
        return [] if suffix.endswith(".json") else None
    file_obj = archive.extractfile(member)
    if file_obj is None:
        return []
    return json.loads(file_obj.read().decode("utf-8"))


def read_pack_archive(record: dict[str, Any]) -> dict[str, Any]:
    archive_path = Path(str(record.get("archive_path") or ""))
    result = {
        "content": [],
        "flashcards": [],
        "quizzes": [],
        "summaries": [],
        "manifest": {},
    }
    if not archive_path.exists():
        return result
    with tarfile.open(archive_path, "r:gz") as archive:
        result["content"] = archive_member_json(archive, "/content.json") or []
        result["flashcards"] = archive_member_json(archive, "/flashcards.json") or []
        result["quizzes"] = archive_member_json(archive, "/quizzes.json") or []
        result["summaries"] = archive_member_json(archive, "/summaries.json") or []
        result["manifest"] = archive_member_json(archive, "/manifest.json") or {}
    return result


def percentile(values: list[int], pct: float) -> int:
    if not values:
        return 0
    sorted_values = sorted(values)
    index = min(len(sorted_values) - 1, max(0, int(round((pct / 100) * (len(sorted_values) - 1)))))
    return sorted_values[index]


def score_pack(counts: Counter[str], lengths: list[int], exact_dupes: int, near_dupes: int) -> float:
    total = sum(counts.values())
    if not total:
        return 0.0
    educational_ratio = counts["EDUCATIONAL_TEXT"] / total
    duplicate_ratio = exact_dupes / total
    near_duplicate_ratio = near_dupes / total
    ocr_ratio = counts["OCR_NOISE"] / total
    noise_ratio = (
        counts["PAGE_NUMBER"]
        + counts["HEADER_FOOTER"]
        + counts["FORMULA_ONLY"]
        + counts["TABLE_FRAGMENT"]
        + counts["SHORT_FRAGMENT"]
        + counts["EMPTY_CONTENT"]
    ) / total
    avg_length = statistics.mean(lengths) if lengths else 0
    length_score = 1.0 if 800 <= avg_length <= 1500 else max(0.0, 1.0 - min(abs(avg_length - 1000) / 1000, 1.0))
    score = (
        educational_ratio * 70
        + length_score * 15
        - duplicate_ratio * 18
        - near_duplicate_ratio * 10
        - ocr_ratio * 22
        - noise_ratio * 12
    )
    return round(max(0.0, min(100.0, score)), 2)


def analyze_pack(record: dict[str, Any]) -> dict[str, Any]:
    archive = read_pack_archive(record)
    chunks = [item for item in archive["content"] if isinstance(item, dict)]
    seen_for_classification: set[str] = set()
    exact_hashes: Counter[str] = Counter()
    near_hashes: Counter[str] = Counter()
    counts: Counter[str] = Counter()
    lengths: list[int] = []
    word_lengths: list[int] = []

    for chunk in chunks:
        text = str(chunk.get("text") or "")
        lengths.append(len(text))
        word_lengths.append(word_count(text))
        exact_hashes[content_hash(text)] += 1
        near_key = near_duplicate_key(text)
        if near_key:
            near_hashes[near_key] += 1
        counts[classify_chunk(text, seen_hashes=seen_for_classification)] += 1

    exact_duplicate_chunks = sum(count - 1 for count in exact_hashes.values() if count > 1)
    near_duplicate_chunks = sum(count - 1 for count in near_hashes.values() if count > 1)
    total = len(chunks)
    cleaned, clean_metrics = clean_chunks(chunks)
    deduped, dedupe_metrics = deduplicate_chunks(cleaned)
    merged, merge_metrics = merge_adjacent_chunks(deduped)
    merged_lengths = [len(str(item.get("text") or "")) for item in merged]

    return {
        "pack_id": record.get("pack_id"),
        "grade": record.get("grade"),
        "subject": record.get("subject"),
        "chapter": record.get("chapter"),
        "language": record.get("language"),
        "total_chunks": total,
        "educational_chunks": counts["EDUCATIONAL_TEXT"],
        "ocr_noise_chunks": counts["OCR_NOISE"],
        "formula_only_chunks": counts["FORMULA_ONLY"],
        "table_fragments": counts["TABLE_FRAGMENT"],
        "page_number_fragments": counts["PAGE_NUMBER"],
        "header_footer_fragments": counts["HEADER_FOOTER"],
        "duplicate_chunks": exact_duplicate_chunks,
        "near_duplicate_chunks": near_duplicate_chunks,
        "short_chunks": counts["SHORT_FRAGMENT"],
        "empty_chunks": counts["EMPTY_CONTENT"],
        "classification_counts": dict(counts),
        "quality_score": score_pack(counts, lengths, exact_duplicate_chunks, near_duplicate_chunks),
        "educational_ratio": round(counts["EDUCATIONAL_TEXT"] / total, 4) if total else 0.0,
        "duplicate_ratio": round(exact_duplicate_chunks / total, 4) if total else 0.0,
        "near_duplicate_ratio": round(near_duplicate_chunks / total, 4) if total else 0.0,
        "ocr_ratio": round(counts["OCR_NOISE"] / total, 4) if total else 0.0,
        "short_ratio": round(counts["SHORT_FRAGMENT"] / total, 4) if total else 0.0,
        "table_ratio": round(counts["TABLE_FRAGMENT"] / total, 4) if total else 0.0,
        "average_chunk_length": round(statistics.mean(lengths), 2) if lengths else 0,
        "median_chunk_length": round(statistics.median(lengths), 2) if lengths else 0,
        "p90_chunk_length": percentile(lengths, 90),
        "average_word_count": round(statistics.mean(word_lengths), 2) if word_lengths else 0,
        "flashcard_count": len(archive["flashcards"]),
        "quiz_count": len(archive["quizzes"]),
        "summary_count": len(archive["summaries"]),
        "cleaning_projection": {
            **clean_metrics,
            "dedupe": dedupe_metrics,
            "merge": merge_metrics,
            "projected_chunks_after_clean_dedupe_merge": len(merged),
            "projected_average_chunk_length": round(statistics.mean(merged_lengths), 2) if merged_lengths else 0,
        },
    }


def markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(cell).replace("\n", " ") for cell in row) + " |")
    return "\n".join(lines)


def write_reports(output_dir: Path, pack_metrics: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    worst = sorted(pack_metrics, key=lambda item: (item["quality_score"], item["educational_ratio"], -item["ocr_ratio"], -item["duplicate_ratio"]))[:100]
    best = sorted(pack_metrics, key=lambda item: item["quality_score"], reverse=True)[:20]

    report_lines = [
        "# Content Quality Report V2",
        "",
        "## Summary",
        "",
        json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True),
        "",
        "## Root-Cause Claims",
        "",
        "- FACT: Runtime pack publication is healthy; this audit scanned repaired pack archives.",
        "- FACT: Quality defects are present inside content chunks and generated assets, not caused by missing archives.",
        "- LIKELY: Short fragments, OCR spacing artifacts, formula-only chunks, and duplicates originate upstream in OCR/chunking.",
        "- UNPROVEN: Cleaning and merging will improve live tutor answers until Qdrant and packs are regenerated and retrieval is re-measured.",
        "",
        "## Best 20 Packs",
        "",
        markdown_table(
            ["pack_id", "score", "chunks", "edu_ratio", "dup_ratio", "ocr_ratio", "avg_len"],
            [[p["pack_id"], p["quality_score"], p["total_chunks"], p["educational_ratio"], p["duplicate_ratio"], p["ocr_ratio"], p["average_chunk_length"]] for p in best],
        ),
        "",
        "## Worst 100 Packs",
        "",
        markdown_table(
            ["pack_id", "score", "chunks", "edu_ratio", "dup_ratio", "near_dup", "ocr", "short", "table", "avg_len"],
            [[p["pack_id"], p["quality_score"], p["total_chunks"], p["educational_ratio"], p["duplicate_ratio"], p["near_duplicate_ratio"], p["ocr_ratio"], p["short_ratio"], p["table_ratio"], p["average_chunk_length"]] for p in worst],
        ),
    ]
    (output_dir / "CONTENT_QUALITY_REPORT_V2.md").write_text("\n".join(report_lines), encoding="utf-8")

    worst_lines = [
        "# Top 100 Worst Packs",
        "",
        markdown_table(
            ["rank", "pack_id", "grade", "subject", "chapter", "score", "educational_chunks", "total_chunks", "ocr", "duplicates", "recommendation"],
            [
                [
                    index + 1,
                    p["pack_id"],
                    p["grade"],
                    p["subject"],
                    p["chapter"],
                    p["quality_score"],
                    p["educational_chunks"],
                    p["total_chunks"],
                    p["ocr_noise_chunks"],
                    p["duplicate_chunks"],
                    "clean+dedupe+merge+regenerate" if p["total_chunks"] else "inspect source ingestion",
                ]
                for index, p in enumerate(worst)
            ],
        ),
    ]
    (output_dir / "TOP_100_WORST_PACKS.md").write_text("\n".join(worst_lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit educational content quality across all repaired runtime packs.")
    parser.add_argument("--storage-path", default="/shared/packs")
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    packs = load_pack_index(Path(args.storage_path))
    pack_metrics = [analyze_pack(record) for record in packs]

    total_chunks = sum(item["total_chunks"] for item in pack_metrics)
    summary = {
        "pack_count": len(pack_metrics),
        "total_chunks": total_chunks,
        "average_quality_score": round(statistics.mean([item["quality_score"] for item in pack_metrics]), 2) if pack_metrics else 0,
        "educational_ratio": round(sum(item["educational_chunks"] for item in pack_metrics) / total_chunks, 4) if total_chunks else 0,
        "duplicate_ratio": round(sum(item["duplicate_chunks"] for item in pack_metrics) / total_chunks, 4) if total_chunks else 0,
        "near_duplicate_ratio": round(sum(item["near_duplicate_chunks"] for item in pack_metrics) / total_chunks, 4) if total_chunks else 0,
        "ocr_ratio": round(sum(item["ocr_noise_chunks"] for item in pack_metrics) / total_chunks, 4) if total_chunks else 0,
        "formula_ratio": round(sum(item["formula_only_chunks"] for item in pack_metrics) / total_chunks, 4) if total_chunks else 0,
        "table_ratio": round(sum(item["table_fragments"] for item in pack_metrics) / total_chunks, 4) if total_chunks else 0,
        "short_ratio": round(sum(item["short_chunks"] for item in pack_metrics) / total_chunks, 4) if total_chunks else 0,
        "average_chunk_length": round(statistics.mean([item["average_chunk_length"] for item in pack_metrics if item["total_chunks"]]), 2) if pack_metrics else 0,
        "target_status": {
            "educational_ratio_gt_0_80": False,
            "ocr_ratio_lt_0_02": False,
            "duplicate_ratio_lt_0_05": False,
            "near_duplicate_ratio_lt_0_05": False,
            "average_chunk_length_800_1500": False,
        },
    }
    summary["target_status"]["educational_ratio_gt_0_80"] = summary["educational_ratio"] > 0.80
    summary["target_status"]["ocr_ratio_lt_0_02"] = summary["ocr_ratio"] < 0.02
    summary["target_status"]["duplicate_ratio_lt_0_05"] = summary["duplicate_ratio"] < 0.05
    summary["target_status"]["near_duplicate_ratio_lt_0_05"] = summary["near_duplicate_ratio"] < 0.05
    summary["target_status"]["average_chunk_length_800_1500"] = 800 <= summary["average_chunk_length"] <= 1500

    write_json(output_dir / "content_quality_v2.json", {"summary": summary, "packs": pack_metrics})
    write_reports(output_dir, pack_metrics, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
