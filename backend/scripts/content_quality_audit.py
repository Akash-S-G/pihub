#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
import tarfile
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


OCR_PATTERNS = (
    "\uf03d",
    "\uf0b4",
    "\uf0a7",
    "\uf0d8",
    "\uf0fc",
    "\u00ad",
    "\ufffd",
    "\x08",
)


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
        return [item for item in data.values() if isinstance(item, dict)]
    return []


def qdrant_post(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def qdrant_scroll(
    qdrant_url: str,
    collection: str,
    limit: int,
    timeout: float,
    point_filter: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    url = f"{qdrant_url.rstrip('/')}/collections/{collection}/points/scroll"
    points: list[dict[str, Any]] = []
    offset: Any = None
    while len(points) < limit:
        batch_limit = min(256, limit - len(points))
        payload: dict[str, Any] = {
            "limit": batch_limit,
            "with_payload": True,
            "with_vector": False,
        }
        if offset is not None:
            payload["offset"] = offset
        if point_filter:
            payload["filter"] = point_filter
        data = qdrant_post(url, payload, timeout)
        result = data.get("result", {})
        batch = result.get("points", [])
        if not batch:
            break
        points.extend(batch)
        offset = result.get("next_page_offset")
        if offset is None:
            break
    return points


def qdrant_filter_for_pack(pack: dict[str, Any]) -> dict[str, Any]:
    must: list[dict[str, Any]] = []
    for key in ("grade", "subject", "chapter"):
        value = pack.get(key)
        if value is not None:
            must.append({"key": key, "match": {"value": value}})
    return {"must": must} if must else {}


def qdrant_count(
    qdrant_url: str,
    collection: str,
    timeout: float,
    point_filter: dict[str, Any] | None = None,
) -> int:
    url = f"{qdrant_url.rstrip('/')}/collections/{collection}/points/count"
    payload: dict[str, Any] = {"exact": True}
    if point_filter:
        payload["filter"] = point_filter
    data = qdrant_post(url, payload, timeout)
    return int(data.get("result", {}).get("count", 0))


def payload_text(payload: dict[str, Any]) -> str:
    for key in ("text", "content", "page_content"):
        value = payload.get(key)
        if isinstance(value, str):
            return value
    return ""


def archive_text(item: dict[str, Any]) -> str:
    metadata = item.get("metadata")
    if isinstance(metadata, dict):
        text = metadata.get("text")
        if isinstance(text, str):
            return text
    text = item.get("text")
    return text if isinstance(text, str) else ""


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def content_hash(text: str) -> str:
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


def length_words(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9]+", text))


def is_page_number(text: str) -> bool:
    stripped = text.strip()
    return bool(re.fullmatch(r"(page\s*(no\.?)?\s*)?\d{1,4}", stripped, flags=re.I))


def is_formula_only(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) > 160:
        return False
    symbols = sum(1 for char in stripped if char in "=+-×÷*/^√∠∆π≤≥<>")
    letters = sum(1 for char in stripped if char.isalpha())
    words = length_words(stripped)
    return symbols >= 1 and words <= 8 and letters < 30


def is_table_fragment(text: str) -> bool:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 4:
        return False
    short_lines = sum(1 for line in lines if len(line) <= 25)
    numeric_lines = sum(1 for line in lines if re.search(r"\d", line))
    return short_lines / len(lines) > 0.65 and numeric_lines / len(lines) > 0.35


def is_ocr_noise(text: str) -> bool:
    stripped = text.strip()
    if any(pattern in stripped for pattern in OCR_PATTERNS):
        return True
    if "�" in stripped:
        return True
    if len(stripped) >= 20:
        alpha = sum(1 for char in stripped if char.isalpha())
        printable = sum(1 for char in stripped if char.isprintable())
        symbolish = len(stripped) - alpha - sum(1 for char in stripped if char.isdigit() or char.isspace())
        if printable and symbolish / max(printable, 1) > 0.45:
            return True
    return False


def classify_text(text: str, seen_hashes: set[str]) -> str:
    stripped = text.strip()
    if not stripped:
        return "EMPTY_CONTENT"
    digest = content_hash(stripped)
    if digest in seen_hashes:
        return "DUPLICATE_CONTENT"
    seen_hashes.add(digest)
    if is_page_number(stripped):
        return "PAGE_NUMBER"
    if is_ocr_noise(stripped):
        return "OCR_NOISE"
    if is_formula_only(stripped):
        return "FORMULA_ONLY"
    if is_table_fragment(stripped):
        return "TABLE_FRAGMENT"
    if len(stripped) < 80 or length_words(stripped) < 12:
        return "SHORT_FRAGMENT"
    return "EDUCATIONAL_TEXT"


def quality_score(class_counts: Counter[str], lengths: list[int]) -> float:
    total = sum(class_counts.values())
    if total == 0:
        return 0.0
    educational_ratio = class_counts["EDUCATIONAL_TEXT"] / total
    duplicate_ratio = class_counts["DUPLICATE_CONTENT"] / total
    empty_ratio = class_counts["EMPTY_CONTENT"] / total
    noise_ratio = (
        class_counts["OCR_NOISE"]
        + class_counts["PAGE_NUMBER"]
        + class_counts["FORMULA_ONLY"]
        + class_counts["TABLE_FRAGMENT"]
        + class_counts["SHORT_FRAGMENT"]
    ) / total
    avg_len = statistics.mean(lengths) if lengths else 0
    length_factor = min(avg_len / 500, 1.0)
    score = (
        educational_ratio * 70
        + length_factor * 20
        - duplicate_ratio * 20
        - noise_ratio * 15
        - empty_ratio * 30
    )
    return round(max(0.0, min(100.0, score)), 2)


def select_packs(packs: list[dict[str, Any]], sample_size: int) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, Any], list[dict[str, Any]]] = defaultdict(list)
    for pack in packs:
        groups[(pack.get("subject"), pack.get("grade"))].append(pack)
    selected: list[dict[str, Any]] = []
    group_values = list(groups.values())
    index = 0
    while len(selected) < sample_size and group_values:
        next_groups: list[list[dict[str, Any]]] = []
        for group in group_values:
            if index < len(group):
                selected.append(group[index])
                if len(selected) >= sample_size:
                    break
            if index + 1 < len(group):
                next_groups.append(group)
        group_values = next_groups
        index += 1
    return selected


def read_archive_content(pack: dict[str, Any]) -> list[dict[str, Any]]:
    archive_path = Path(str(pack.get("archive_path") or ""))
    if not archive_path.exists():
        return []
    with tarfile.open(archive_path, "r:gz") as archive:
        member = next((item for item in archive.getmembers() if item.name.endswith("/content.json")), None)
        if member is None:
            return []
        file_obj = archive.extractfile(member)
        if file_obj is None:
            return []
        data = json.loads(file_obj.read().decode("utf-8"))
    return data if isinstance(data, list) else []


def pack_quality(pack: dict[str, Any], content_items: list[dict[str, Any]]) -> dict[str, Any]:
    seen: set[str] = set()
    counts: Counter[str] = Counter()
    lengths: list[int] = []
    samples: dict[str, str] = {}
    for item in content_items:
        text = archive_text(item)
        category = classify_text(text, seen)
        counts[category] += 1
        lengths.append(len(text))
        samples.setdefault(category, text[:300])
    total = sum(counts.values())
    score = quality_score(counts, lengths)
    return {
        "pack_id": pack.get("pack_id"),
        "subject": pack.get("subject"),
        "grade": pack.get("grade"),
        "chapter": pack.get("chapter"),
        "archive_path": pack.get("archive_path"),
        "chunk_count": len(content_items),
        "quality_score": score,
        "educational_ratio": round(counts["EDUCATIONAL_TEXT"] / total, 4) if total else 0,
        "ocr_noise_ratio": round(counts["OCR_NOISE"] / total, 4) if total else 0,
        "duplicate_ratio": round(counts["DUPLICATE_CONTENT"] / total, 4) if total else 0,
        "empty_ratio": round(counts["EMPTY_CONTENT"] / total, 4) if total else 0,
        "classification_counts": dict(counts),
        "length": {
            "average": round(statistics.mean(lengths), 2) if lengths else 0,
            "minimum": min(lengths) if lengths else 0,
            "maximum": max(lengths) if lengths else 0,
        },
        "samples": samples,
    }


def integrity_for_pack(
    qdrant_url: str,
    collection: str,
    pack: dict[str, Any],
    archive_items: list[dict[str, Any]],
    timeout: float,
) -> dict[str, Any]:
    archive_ids = [str(item.get("chunk_id")) for item in archive_items if item.get("chunk_id")]
    archive_counter = Counter(archive_ids)
    point_filter = qdrant_filter_for_pack(pack)
    qdrant_points = qdrant_scroll(
        qdrant_url,
        collection,
        max(len(archive_ids) + 500, 1000),
        timeout,
        point_filter,
    )
    exact_qdrant_count = qdrant_count(qdrant_url, collection, timeout, point_filter)
    qdrant_ids = {str(point.get("id")) for point in qdrant_points}
    missing_chunks = [chunk_id for chunk_id in archive_ids if chunk_id not in qdrant_ids]
    duplicate_chunks = [chunk_id for chunk_id, count in archive_counter.items() if count > 1]
    return {
        "pack_id": pack.get("pack_id"),
        "subject": pack.get("subject"),
        "grade": pack.get("grade"),
        "chapter": pack.get("chapter"),
        "chunk_count_qdrant": exact_qdrant_count,
        "chunk_count_archive": len(archive_ids),
        "missing_chunk_count": len(missing_chunks),
        "duplicate_chunk_count": len(duplicate_chunks),
        "missing_chunks_sample": missing_chunks[:50],
        "duplicate_chunks_sample": duplicate_chunks[:50],
        "note": "Qdrant comparison uses exact grade/subject/chapter metadata filter; non-zero missing can indicate metadata normalization mismatch.",
    }


def markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(cell).replace("\n", " ") for cell in row) + " |")
    return "\n".join(lines)


def write_quality_report(path: Path, report: dict[str, Any]) -> None:
    rows = []
    for item in report["chapter_quality"][:30]:
        rows.append([
            item["pack_id"],
            item["grade"],
            item["subject"],
            item["chapter"],
            item["chunk_count"],
            item["quality_score"],
            item["educational_ratio"],
            item["ocr_noise_ratio"],
            item["duplicate_ratio"],
        ])
    text = [
        "# Content Quality Audit Report",
        "",
        f"Sampled packs: {report['summary']['sampled_packs']}",
        f"Sampled archive chunks: {report['summary']['sampled_archive_chunks']}",
        f"Average quality score: {report['summary']['average_quality_score']}",
        f"Overall educational ratio: {report['summary']['overall_educational_ratio']}",
        f"Overall OCR noise ratio: {report['summary']['overall_ocr_noise_ratio']}",
        "",
        "## Chapter Sample",
        "",
        markdown_table(
            ["pack_id", "grade", "subject", "chapter", "chunks", "score", "edu_ratio", "ocr_ratio", "dup_ratio"],
            rows,
        ),
        "",
        "## Evidence Samples",
    ]
    for item in report["chapter_quality"][:10]:
        text.append(f"\n### {item['pack_id']}")
        text.append(json.dumps(item.get("samples", {}), indent=2, ensure_ascii=False))
    path.write_text("\n".join(text), encoding="utf-8")


def write_integrity_report(path: Path, results: list[dict[str, Any]]) -> None:
    rows = [
        [
            item["pack_id"],
            item["chunk_count_qdrant"],
            item["chunk_count_archive"],
            item["missing_chunk_count"],
            item["duplicate_chunk_count"],
        ]
        for item in results
    ]
    text = [
        "# Pack Content Integrity Report",
        "",
        markdown_table(["pack_id", "chunk_count_qdrant", "chunk_count_archive", "missing_chunks", "duplicate_chunks"], rows),
        "",
        "## Non-Zero Issues",
    ]
    issues = [item for item in results if item["missing_chunk_count"] or item["duplicate_chunk_count"]]
    text.append(json.dumps(issues[:50], indent=2, ensure_ascii=False))
    path.write_text("\n".join(text), encoding="utf-8")


def write_ranking_report(path: Path, chapter_quality: list[dict[str, Any]]) -> None:
    ranked = sorted(chapter_quality, key=lambda item: item["quality_score"], reverse=True)
    best = ranked[:20]
    worst = list(reversed(ranked[-20:]))
    def rows(items: list[dict[str, Any]]) -> list[list[Any]]:
        return [
            [
                item["pack_id"],
                item["grade"],
                item["subject"],
                item["chapter"],
                item["quality_score"],
                item["educational_ratio"],
                item["ocr_noise_ratio"],
                item["duplicate_ratio"],
            ]
            for item in items
        ]
    text = [
        "# Content Quality Ranking",
        "",
        "## Top 20 Best Chapters",
        "",
        markdown_table(["pack_id", "grade", "subject", "chapter", "score", "edu_ratio", "ocr_ratio", "dup_ratio"], rows(best)),
        "",
        "## Bottom 20 Worst Chapters",
        "",
        markdown_table(["pack_id", "grade", "subject", "chapter", "score", "edu_ratio", "ocr_ratio", "dup_ratio"], rows(worst)),
    ]
    path.write_text("\n".join(text), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit PIHUB runtime pack content quality without mutating content.")
    parser.add_argument("--storage-path", default="/shared/packs")
    parser.add_argument("--qdrant-url", default="http://qdrant:6333")
    parser.add_argument("--collection", default="educational_chunks")
    parser.add_argument("--sample-packs", type=int, default=100)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    packs = load_pack_index(Path(args.storage_path))
    sampled = select_packs(packs, min(args.sample_packs, len(packs)))

    chapter_quality: list[dict[str, Any]] = []
    integrity: list[dict[str, Any]] = []
    total_counts: Counter[str] = Counter()
    archive_chunk_total = 0

    for pack in sampled:
        content_items = read_archive_content(pack)
        quality = pack_quality(pack, content_items)
        chapter_quality.append(quality)
        total_counts.update(quality["classification_counts"])
        archive_chunk_total += len(content_items)
        integrity.append(integrity_for_pack(args.qdrant_url, args.collection, pack, content_items, args.timeout))

    total_classified = sum(total_counts.values())
    report = {
        "summary": {
            "total_runtime_packs": len(packs),
            "sampled_packs": len(sampled),
            "sampled_archive_chunks": archive_chunk_total,
            "average_quality_score": round(statistics.mean([item["quality_score"] for item in chapter_quality]), 2) if chapter_quality else 0,
            "overall_educational_ratio": round(total_counts["EDUCATIONAL_TEXT"] / total_classified, 4) if total_classified else 0,
            "overall_ocr_noise_ratio": round(total_counts["OCR_NOISE"] / total_classified, 4) if total_classified else 0,
            "overall_duplicate_ratio": round(total_counts["DUPLICATE_CONTENT"] / total_classified, 4) if total_classified else 0,
            "overall_empty_ratio": round(total_counts["EMPTY_CONTENT"] / total_classified, 4) if total_classified else 0,
            "classification_counts": dict(total_counts),
        },
        "chapter_quality": chapter_quality,
    }

    write_json(output_dir / "content_quality_audit.json", report)
    write_json(output_dir / "pack_content_integrity.json", integrity)
    write_quality_report(output_dir / "CONTENT_QUALITY_AUDIT_REPORT.md", report)
    write_integrity_report(output_dir / "PACK_CONTENT_INTEGRITY_REPORT.md", integrity)
    write_ranking_report(output_dir / "CONTENT_QUALITY_RANKING.md", chapter_quality)
    print(json.dumps(report["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
