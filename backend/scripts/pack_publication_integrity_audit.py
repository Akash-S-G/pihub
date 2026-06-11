#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import tarfile
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any


REQUIRED_ARCHIVE_FILES = {
    "content.json",
    "flashcards.json",
    "glossary.json",
    "manifest.json",
    "quizzes.json",
    "summaries.json",
    "enrichment.json",
    "retrieval_index/index.json",
}

SUBJECT_ALIASES = {
    "math": ["math", "maths", "mathematics"],
    "maths": ["maths", "mathematics"],
    "mathematics": ["mathematics", "maths"],
    "science": ["science", "social_science"],
    "social_science": ["social_science", "science"],
    "social science": ["social_science", "science"],
    "history": ["social_science", "history"],
    "geography": ["social_science", "geography"],
    "economics": ["social_science", "economics"],
    "civics": ["social_science", "civics"],
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def load_pack_index(storage_path: Path) -> list[dict[str, Any]]:
    data = load_json(storage_path / "pack_index.json")
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict) and isinstance(data.get("packs"), list):
        return [item for item in data["packs"] if isinstance(item, dict)]
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


def qdrant_count(qdrant_url: str, collection: str, filters: dict[str, Any], timeout: float) -> int:
    payload: dict[str, Any] = {"exact": True}
    if filters:
        payload["filter"] = filters
    data = qdrant_post(f"{qdrant_url.rstrip('/')}/collections/{collection}/points/count", payload, timeout)
    return int(data.get("result", {}).get("count", 0))


def qdrant_scroll_ids(qdrant_url: str, collection: str, filters: dict[str, Any], limit: int, timeout: float) -> set[str]:
    url = f"{qdrant_url.rstrip('/')}/collections/{collection}/points/scroll"
    ids: set[str] = set()
    offset: Any = None
    while len(ids) < limit:
        payload: dict[str, Any] = {
            "limit": min(256, limit - len(ids)),
            "with_payload": False,
            "with_vector": False,
        }
        if filters:
            payload["filter"] = filters
        if offset is not None:
            payload["offset"] = offset
        data = qdrant_post(url, payload, timeout)
        result = data.get("result", {})
        points = result.get("points", [])
        if not points:
            break
        ids.update(str(point.get("id")) for point in points if point.get("id") is not None)
        offset = result.get("next_page_offset")
        if offset is None:
            break
    return ids


def qdrant_metadata_counts(qdrant_url: str, collection: str, timeout: float) -> Counter[tuple[Any, Any, Any, Any]]:
    url = f"{qdrant_url.rstrip('/')}/collections/{collection}/points/scroll"
    counts: Counter[tuple[Any, Any, Any, Any]] = Counter()
    offset: Any = None
    while True:
        payload: dict[str, Any] = {
            "limit": 1000,
            "with_payload": True,
            "with_vector": False,
        }
        if offset is not None:
            payload["offset"] = offset
        data = qdrant_post(url, payload, timeout)
        result = data.get("result", {})
        points = result.get("points", [])
        if not points:
            break
        for point in points:
            item = point.get("payload") or {}
            counts[(item.get("grade"), item.get("subject"), item.get("chapter"), item.get("language"))] += 1
        offset = result.get("next_page_offset")
        if offset is None:
            break
    return counts


def normalize_dash(value: str | None) -> str | None:
    if value is None:
        return None
    return str(value).replace("\u2013", "-").replace("\u2014", "-").strip()


def filter_from_values(grade: Any, subject: Any, chapter: Any, language: Any) -> dict[str, Any]:
    must: list[dict[str, Any]] = []
    for key, value in (("grade", grade), ("subject", subject), ("chapter", chapter), ("language", language)):
        if value not in (None, ""):
            must.append({"key": key, "match": {"value": value}})
    return {"must": must} if must else {}


def qdrant_count_variants(
    metadata_counts: Counter[tuple[Any, Any, Any, Any]],
    record: dict[str, Any],
    manifest: dict[str, Any] | None,
) -> dict[str, Any]:
    generation = (manifest or {}).get("generation_metadata", {}) if manifest else {}
    grade = record.get("grade")
    language = record.get("language")
    subjects = [
        record.get("subject"),
        generation.get("subject"),
        (manifest or {}).get("subject") if manifest else None,
    ]
    chapters = [
        record.get("chapter"),
        generation.get("chapter"),
        (manifest or {}).get("chapter") if manifest else None,
    ]
    expanded_subjects: list[Any] = []
    for subject in subjects:
        if subject in (None, ""):
            continue
        expanded_subjects.append(subject)
        expanded_subjects.append(normalize_dash(str(subject)))
        expanded_subjects.extend(SUBJECT_ALIASES.get(str(subject), []))
    expanded_chapters: list[Any] = []
    for chapter in chapters:
        if chapter in (None, ""):
            continue
        expanded_chapters.append(chapter)
        expanded_chapters.append(normalize_dash(str(chapter)))
    subject_values = list(dict.fromkeys(value for value in expanded_subjects if value not in (None, "")))
    chapter_values = list(dict.fromkeys(value for value in expanded_chapters if value not in (None, "")))

    record_subject = record.get("subject")
    record_chapter = record.get("chapter")
    generator_exact_count = metadata_counts[(grade, record_subject, record_chapter, language)]

    generator_variants: list[dict[str, Any]] = []
    available_variants: list[dict[str, Any]] = []
    fallback_attempts: list[dict[str, Any]] = []

    def count_exact(subject: Any, chapter: Any, item_language: Any) -> int:
        return metadata_counts[(grade, subject, chapter, item_language)]

    def count_without_language(subject: Any, chapter: Any) -> int:
        return sum(
            count
            for (item_grade, item_subject, item_chapter, _item_language), count in metadata_counts.items()
            if item_grade == grade and item_subject == subject and item_chapter == chapter
        )

    def add_fallback(reason: str, subject: Any, chapter: Any, item_language: Any, count: int) -> None:
        if subject in (None, "") or chapter in (None, ""):
            return
        fallback_attempts.append({
            "reason": reason,
            "grade": grade,
            "subject": subject,
            "chapter": chapter,
            "language": item_language if item_language is not None else "*",
            "count": int(count),
        })

    add_fallback("exact_filter", record_subject, record_chapter, language, generator_exact_count)
    if language not in (None, ""):
        add_fallback("remove_language_filter", record_subject, record_chapter, None, count_without_language(record_subject, record_chapter))
    for subject in subject_values:
        if subject == record_subject:
            continue
        add_fallback("normalized_subject_filter", subject, record_chapter, language, count_exact(subject, record_chapter, language))
        if language not in (None, ""):
            add_fallback("normalized_subject_without_language", subject, record_chapter, None, count_without_language(subject, record_chapter))

    fallback_best = next((attempt for attempt in fallback_attempts if attempt["count"] > 0), None)
    for subject in subject_values or [None]:
        for chapter in chapter_values or [None]:
            generator_count = metadata_counts[(grade, subject, chapter, language)]
            available_count = sum(
                count
                for (item_grade, item_subject, item_chapter, _item_language), count in metadata_counts.items()
                if item_grade == grade and item_subject == subject and item_chapter == chapter
            )
            generator_variants.append({
                "grade": grade,
                "subject": subject,
                "chapter": chapter,
                "language": language,
                "count": generator_count,
            })
        available_variants.append({
                "grade": grade,
                "subject": subject,
                "chapter": chapter,
                "language": "*",
                "count": available_count,
            })
    generator_variants.sort(key=lambda item: item["count"], reverse=True)
    available_variants.sort(key=lambda item: item["count"], reverse=True)
    generator_best = generator_variants[0] if generator_variants else {"count": 0}
    available_best = available_variants[0] if available_variants else {"count": 0}
    if generation.get("legacy_exact_metadata_repair"):
        effective_generator = generator_best
        if fallback_best is not None and int(fallback_best.get("count", 0)) > int(generator_best.get("count", 0)):
            effective_generator = fallback_best
    else:
        effective_generator = fallback_best if fallback_best is not None else generator_best
    return {
        "qdrant_generator_exact_count": generator_exact_count,
        "qdrant_generator_count": int(effective_generator.get("count", 0)),
        "qdrant_generator_filter": effective_generator,
        "qdrant_legacy_generator_count": int(generator_best.get("count", 0)),
        "qdrant_legacy_generator_filter": generator_best,
        "qdrant_available_count": int(available_best.get("count", 0)),
        "qdrant_available_filter": available_best,
        "qdrant_fallback_attempts": fallback_attempts,
    }


def archive_member_lookup(archive: tarfile.TarFile) -> dict[str, tarfile.TarInfo]:
    lookup: dict[str, tarfile.TarInfo] = {}
    for member in archive.getmembers():
        if not member.isfile():
            continue
        parts = member.name.split("/", 1)
        relative = parts[1] if len(parts) == 2 else parts[0]
        lookup[relative] = member
    return lookup


def load_archive_json(archive: tarfile.TarFile, member: tarfile.TarInfo) -> Any:
    file_obj = archive.extractfile(member)
    if file_obj is None:
        raise ValueError(f"cannot extract {member.name}")
    return json.loads(file_obj.read().decode("utf-8"))


def inspect_pack_archive(record: dict[str, Any]) -> dict[str, Any]:
    archive_path = Path(str(record.get("archive_path") or ""))
    pack_dir = Path(str(record.get("pack_dir") or ""))
    result: dict[str, Any] = {
        "archive_exists": archive_path.exists(),
        "archive_path": str(archive_path),
        "pack_dir_exists": pack_dir.exists(),
        "manifest_path": str(pack_dir / "manifest.json"),
        "missing_files": [],
        "empty_files": [],
        "corruption_errors": [],
        "archive_chunk_count": 0,
        "manifest_chunk_count": None,
        "manifest": None,
        "archive_chunk_ids_sample": [],
        "archive_duplicate_chunk_count": 0,
    }
    if not archive_path.exists():
        result["corruption_errors"].append("archive:not-found")
        return result
    try:
        with tarfile.open(archive_path, "r:gz") as archive:
            members = archive_member_lookup(archive)
            missing = sorted(REQUIRED_ARCHIVE_FILES - set(members))
            result["missing_files"] = missing
            for filename, member in members.items():
                if filename in REQUIRED_ARCHIVE_FILES and member.size == 0:
                    result["empty_files"].append(filename)
            if "content.json" in members:
                content = load_archive_json(archive, members["content.json"])
                if not isinstance(content, list):
                    result["corruption_errors"].append("content:not-list")
                    content = []
                ids = [str(item.get("chunk_id")) for item in content if isinstance(item, dict) and item.get("chunk_id")]
                result["archive_chunk_count"] = len(content)
                result["archive_chunk_ids_sample"] = ids[:20]
                counts = Counter(ids)
                result["archive_duplicate_chunk_count"] = sum(1 for count in counts.values() if count > 1)
            if "manifest.json" in members:
                manifest = load_archive_json(archive, members["manifest.json"])
                result["manifest"] = manifest if isinstance(manifest, dict) else None
                if isinstance(manifest, dict):
                    result["manifest_chunk_count"] = int((manifest.get("artifact_counts") or {}).get("content", 0))
    except (tarfile.TarError, json.JSONDecodeError, OSError, ValueError) as exc:
        result["corruption_errors"].append(f"archive:corrupted:{exc}")
    return result


def classify_publication(row: dict[str, Any]) -> str:
    if row["corruption_errors"] or row["missing_files"] or row["empty_files"]:
        return "CORRUPTED"
    if row["manifest_chunk_count"] is None:
        return "MISSING_MANIFEST"
    if row["manifest_chunk_count"] != row["archive_chunk_count"]:
        return "CORRUPTED"
    qdrant_available = row["qdrant_available_count"]
    qdrant_generator = row["qdrant_generator_count"]
    archive = row["archive_chunk_count"]
    if qdrant_available > 0 and qdrant_generator == 0:
        return "METADATA_MISMATCH"
    if qdrant_generator > 0 and archive == 0:
        return "EMPTY_ARCHIVE"
    if qdrant_generator > 0 and archive > 0 and archive < qdrant_generator:
        return "PARTIAL_ARCHIVE"
    if qdrant_generator > 0 and archive == qdrant_generator:
        return "GOOD"
    if qdrant_available > archive and qdrant_generator == archive:
        return "GOOD"
    if qdrant_available == 0 and archive > 0:
        return "METADATA_MISMATCH"
    return "GOOD"


def repair_class(status: str) -> str:
    if status == "GOOD":
        return "GOOD"
    if status in {"MISSING_MANIFEST", "CORRUPTED"}:
        return "REPAIRABLE"
    return "REGENERATE_REQUIRED"


def command_for_pack(row: dict[str, Any]) -> str:
    payload = {
        "pack_type": "chapter" if row.get("chapter") else "class",
        "grade": row.get("grade"),
        "subject": row.get("qdrant_available_filter", {}).get("subject") or row.get("subject"),
        "chapter": row.get("qdrant_available_filter", {}).get("chapter") or row.get("chapter"),
        "language": row.get("language") or "english",
    }
    payload = {key: value for key, value in payload.items() if value is not None}
    return (
        "curl -sS -X POST http://pack-service:8030/packs/generate "
        "-H 'Content-Type: application/json' "
        f"-d '{json.dumps(payload, ensure_ascii=False)}'"
    )


def markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(cell).replace("\n", " ") for cell in row) + " |")
    return "\n".join(lines)


def write_integrity_report(path: Path, rows: list[dict[str, Any]], summary: dict[str, Any], evidence: dict[str, Any]) -> None:
    status_rows = [[status, count] for status, count in sorted(summary["status_counts"].items())]
    sample_rows = [
        [
            row["pack_id"],
            row["grade"],
            row["subject"],
            row["chapter"],
            row["qdrant_available_count"],
            row["qdrant_generator_count"],
            row["archive_chunk_count"],
            row["manifest_chunk_count"],
            row["publication_status"],
            row["repair_class"],
        ]
        for row in rows[:120]
    ]
    text = [
        "# Pack Publication Integrity Report",
        "",
        "## Summary",
        "",
        json.dumps(summary, indent=2, ensure_ascii=False),
        "",
        "## Status Counts",
        "",
        markdown_table(["status", "count"], status_rows),
        "",
        "## Root-Cause Evidence",
        "",
        json.dumps(evidence, indent=2, ensure_ascii=False),
        "",
        "## Pack Inventory Sample",
        "",
        markdown_table(
            ["pack_id", "grade", "subject", "chapter", "qdrant_available", "generator_receives", "archive", "manifest", "status", "repair"],
            sample_rows,
        ),
    ]
    path.write_text("\n".join(text), encoding="utf-8")


def write_top_broken_report(path: Path, rows: list[dict[str, Any]]) -> None:
    broken = [row for row in rows if row["publication_status"] != "GOOD"]
    broken.sort(key=lambda row: (row["qdrant_available_count"] - row["archive_chunk_count"], row["qdrant_available_count"]), reverse=True)
    table = [
        [
            row["pack_id"],
            row["qdrant_available_count"],
            row["archive_chunk_count"],
            row["manifest_chunk_count"],
            row["publication_status"],
            row["repair_class"],
        ]
        for row in broken[:50]
    ]
    text = [
        "# Top 50 Broken Packs",
        "",
        markdown_table(["pack_id", "expected_chunks", "actual_chunks", "manifest_chunks", "status", "repair_recommendation"], table),
    ]
    path.write_text("\n".join(text), encoding="utf-8")


def write_regeneration_plan(path: Path, rows: list[dict[str, Any]]) -> None:
    regenerate = [row for row in rows if row["repair_class"] == "REGENERATE_REQUIRED"]
    repairable = [row for row in rows if row["repair_class"] == "REPAIRABLE"]
    lines = [
        "# Pack Regeneration Plan",
        "",
        f"Regenerate required: {len(regenerate)}",
        f"Repairable without full regeneration: {len(repairable)}",
        "",
        "## Regenerate Only Damaged Packs",
        "",
        "Run from inside the Docker network, for example from `pihub-pack-service` or another service container.",
        "",
        "```bash",
    ]
    for row in regenerate:
        lines.append(command_for_pack(row))
    lines.extend([
        "```",
        "",
        "## Repairable Packs",
        "",
        "These have missing/corrupted artifacts or manifest mismatch and may be repairable from existing pack directories if content.json is intact.",
        "",
        json.dumps([
            {
                "pack_id": row["pack_id"],
                "status": row["publication_status"],
                "missing_files": row["missing_files"],
                "empty_files": row["empty_files"],
                "corruption_errors": row["corruption_errors"],
            }
            for row in repairable
        ], indent=2, ensure_ascii=False),
    ])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit PIHUB pack publication integrity across Qdrant, archives, manifests, and pack index.")
    parser.add_argument("--storage-path", default="/shared/packs")
    parser.add_argument("--qdrant-url", default="http://qdrant:6333")
    parser.add_argument("--collection", default="educational_chunks")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    records = load_pack_index(Path(args.storage_path))
    metadata_counts = qdrant_metadata_counts(args.qdrant_url, args.collection, args.timeout)
    rows: list[dict[str, Any]] = []
    for record in records:
        archive = inspect_pack_archive(record)
        manifest = archive["manifest"]
        counts = qdrant_count_variants(metadata_counts, record, manifest)
        row = {
            "pack_id": record.get("pack_id"),
            "grade": record.get("grade"),
            "subject": record.get("subject"),
            "chapter": record.get("chapter"),
            "language": record.get("language"),
            "version": record.get("version"),
            "qdrant_generator_exact_count": counts["qdrant_generator_exact_count"],
            "qdrant_generator_count": counts["qdrant_generator_count"],
            "qdrant_generator_filter": counts["qdrant_generator_filter"],
            "qdrant_available_count": counts["qdrant_available_count"],
            "qdrant_available_filter": counts["qdrant_available_filter"],
            "archive_chunk_count": archive["archive_chunk_count"],
            "manifest_chunk_count": archive["manifest_chunk_count"],
            "manifest_artifact_counts": (manifest or {}).get("artifact_counts", {}),
            "missing_files": archive["missing_files"],
            "empty_files": archive["empty_files"],
            "corruption_errors": archive["corruption_errors"],
            "archive_duplicate_chunk_count": archive["archive_duplicate_chunk_count"],
            "archive_path": archive["archive_path"],
            "manifest_path": archive["manifest_path"],
        }
        row["publication_status"] = classify_publication(row)
        row["repair_class"] = repair_class(row["publication_status"])
        rows.append(row)

    status_counts = Counter(row["publication_status"] for row in rows)
    repair_counts = Counter(row["repair_class"] for row in rows)
    summary = {
        "total_packs": len(rows),
        "qdrant_metadata_groups": len(metadata_counts),
        "qdrant_chunks_counted": sum(metadata_counts.values()),
        "good_packs": status_counts["GOOD"],
        "empty_packs": status_counts["EMPTY_ARCHIVE"],
        "partial_packs": status_counts["PARTIAL_ARCHIVE"],
        "corrupted_packs": status_counts["CORRUPTED"],
        "metadata_mismatch_packs": status_counts["METADATA_MISMATCH"],
        "missing_manifest_packs": status_counts["MISSING_MANIFEST"],
        "status_counts": dict(status_counts),
        "repair_counts": dict(repair_counts),
    }
    evidence = {
        "generator_filtering": (
            "PackGenerator._search_chunks_by_metadata builds exact Qdrant filters for grade, subject, chapter, language. "
            "If incoming metadata differs from Qdrant payload metadata, or Qdrant chunks omit language while the generator "
            "filters language=english, it returns zero chunks."
        ),
        "generator_receives_chunks": (
            "qdrant_generator_count in this report estimates how many chunks the current generator filter can receive. "
            "qdrant_available_count estimates how many chunks exist for the grade/subject/chapter regardless of language."
        ),
        "empty_archive_behavior": (
            "PackGenerator._create_pack accepts an empty chunk list. PackRepository.save_pack writes content.json=[], "
            "manifest artifact_counts.content=0, creates an archive, and registers it in pack_index.json."
        ),
        "archive_writer": (
            "PackRepository._write_artifacts always writes content.json, glossary.json, quizzes.json, flashcards.json, "
            "summaries.json, enrichment.json, retrieval_index/index.json, then archives the directory with tar.gz."
        ),
        "manifest_accuracy_rule": "manifest.artifact_counts.content must equal content.json record count.",
    }

    write_json(output_dir / "pack_publication_integrity.json", rows)
    write_integrity_report(output_dir / "PACK_PUBLICATION_INTEGRITY_REPORT.md", rows, summary, evidence)
    write_top_broken_report(output_dir / "TOP_50_BROKEN_PACKS.md", rows)
    write_regeneration_plan(output_dir / "PACK_REGENERATION_PLAN.md", rows)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
