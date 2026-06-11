#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from app.pack_generator import PackGenerationNoContentError, PackGenerator, PackQualityGateError
from app.pack_storage.pack_repository import PackRepository
from content_forensics.run_grade8_full_regeneration import (
    PACK_STORAGE_PATH,
    QDRANT_COLLECTION,
    QDRANT_URL,
    CURRICULUM_GRAPH_PATH,
    average,
    duplicate_publication_targets,
    load_json,
    quality_metrics,
    regenerate_record,
)


OUT_DIR = Path("/shared/multi_grade_regeneration")
GRADES = (6, 7, 9, 10)
GRADE8_BASELINE = {
    "tutor_quality": 93.86,
    "reader_quality": 98.59,
    "summary_quality": 90.27,
    "quiz_quality": 100.0,
    "flashcard_quality": 93.12,
    "quality_gate_pass_rate": 100.0,
    "publication_rate": 94.0,
    "formula_coverage": 100.0,
    "concept_coverage": 100.0,
}


def write_json(name: str, payload: Any) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / name).write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def grade_records(repository: PackRepository, grade: int) -> list[dict[str, Any]]:
    records = [record for record in repository.list_packs() if str(record.get("grade")) == str(grade)]
    by_id = {str(record.get("pack_id")): record for record in records if record.get("pack_id")}
    return [by_id[key] for key in sorted(by_id)]


def inventory(records: list[dict[str, Any]], grade: int) -> dict[str, Any]:
    subjects = Counter(str(record.get("subject") or "unknown") for record in records)
    chapters = [str(record.get("chapter") or "") for record in records if record.get("chapter")]
    source_pdf_like = [
        record.get("chapter")
        for record in records
        if ".pdf" in str(record.get("chapter") or "").lower() or ".pdf" in str(record.get("pack_id") or "").lower()
    ]
    return {
        "grade": grade,
        "pack_count": len(records),
        "subject_count": len(subjects),
        "chapter_count": len(set(chapters)),
        "subjects": dict(sorted(subjects.items())),
        "chapters": sorted(set(chapters)),
        "source_pdfs": sorted(set(str(item) for item in source_pdf_like if item)),
        "rows": [
            {
                "pack_id": record.get("pack_id"),
                "subject": record.get("subject"),
                "chapter": record.get("chapter"),
                "language": record.get("language"),
                "artifact_counts": record.get("artifact_counts"),
            }
            for record in records
        ],
    }


async def regenerate_grade(generator: PackGenerator, grade: int, targets: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    started = time.time()
    for index, record in enumerate(targets, start=1):
        print(json.dumps({"event": "MULTI_GRADE_REGENERATION_START", "grade": grade, "index": index, "total": len(targets), "pack_id": record.get("pack_id")}))
        row = await regenerate_record_for_grade(generator, grade, record)
        print(json.dumps({"event": "MULTI_GRADE_REGENERATION_END", "grade": grade, "pack_id": row.get("pack_id"), "status": row.get("status")}))
        rows.append(row)
    published_ids = {row.get("generated_pack_id") for row in rows if row.get("status") == "published"}
    refreshed = grade_records(generator.repository, grade)
    published_records = [record for record in refreshed if record.get("pack_id") in published_ids]
    metrics = quality_metrics(published_records)
    coverage = coverage_metrics(published_records)
    rejected = [row for row in rows if row.get("status") == "rejected"]
    failed = [row for row in rows if row.get("status") == "failed"]
    return {
        "grade": grade,
        "duration_ms": round((time.time() - started) * 1000, 2),
        "packs_targeted": len(targets),
        "packs_regenerated": sum(1 for row in rows if row.get("status") == "published"),
        "packs_published": len(published_records),
        "packs_rejected": len(rejected),
        "packs_failed": len(failed),
        "publication_rate": round(100.0 * len(published_records) / max(1, len(targets)), 2),
        "quality_metrics": {**metrics, **coverage},
        "duplicate_publication_targets": duplicate_publication_targets(rows),
        "failure_analysis": [failure_record(row, grade) for row in [*rejected, *failed]],
        "rows": rows,
    }


async def regenerate_record_for_grade(generator: PackGenerator, grade: int, record: dict[str, Any]) -> dict[str, Any]:
    pack_id = str(record.get("pack_id") or "")
    subject = str(record.get("subject") or "")
    chapter = record.get("chapter")
    language = str(record.get("language") or "english")
    before_counts = dict(record.get("artifact_counts") or {})
    started = time.time()
    try:
        if chapter:
            generated_id = await generator.generate_chapter_pack(
                grade=grade,
                subject=subject,
                chapter=str(chapter),
                language=language,
                compression="gzip",
                quantize_embeddings=False,
            )
        else:
            generated_id = await generator.generate_class_pack(
                grade=grade,
                subject=subject,
                language=language,
                include_media=False,
                compression="gzip",
                quantize_embeddings=False,
            )
        new_record = generator.repository.get_pack(generated_id) or {}
        from content_forensics.run_grade8_full_regeneration import validate_artifacts

        return {
            "pack_id": pack_id,
            "generated_pack_id": generated_id,
            "grade": grade,
            "subject": subject,
            "chapter": chapter,
            "language": language,
            "status": "published",
            "duration_ms": round((time.time() - started) * 1000, 2),
            "before_artifact_counts": before_counts,
            "after_artifact_counts": dict(new_record.get("artifact_counts") or {}),
            "quality_gate": load_json(Path(str(new_record.get("pack_dir") or "")) / "reports" / "quality_gate.json") or {},
            "artifact_validation": validate_artifacts(new_record),
        }
    except (PackGenerationNoContentError, PackQualityGateError) as exc:
        return {
            "pack_id": pack_id,
            "grade": grade,
            "subject": subject,
            "chapter": chapter,
            "language": language,
            "status": "rejected",
            "duration_ms": round((time.time() - started) * 1000, 2),
            "error_type": type(exc).__name__,
            "error": str(exc),
            "before_artifact_counts": before_counts,
        }
    except Exception as exc:
        return {
            "pack_id": pack_id,
            "grade": grade,
            "subject": subject,
            "chapter": chapter,
            "language": language,
            "status": "failed",
            "duration_ms": round((time.time() - started) * 1000, 2),
            "error_type": type(exc).__name__,
            "error": str(exc),
            "before_artifact_counts": before_counts,
        }


def coverage_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    concept = []
    formula = []
    for record in records:
        report = load_json(Path(str(record.get("pack_dir") or "")) / "reports" / "concept_coverage_report.json") or {}
        concept.append(float(report.get("coverage_percent") or 0.0))
        formula.append(float(report.get("formula_coverage_percent") or 100.0))
    return {
        "concept_coverage": average(concept),
        "formula_coverage": average(formula),
    }


def failure_record(row: dict[str, Any], grade: int) -> dict[str, Any]:
    reason = str(row.get("error") or "")
    return {
        "pack_id": row.get("pack_id"),
        "grade": grade,
        "subject": row.get("subject"),
        "chapter": row.get("chapter"),
        "failure_reason": reason,
        "failure_class": classify_failure(row),
        "quality_metrics": (row.get("quality_gate") or {}).get("metrics", {}),
        "error_type": row.get("error_type"),
    }


def classify_failure(row: dict[str, Any]) -> str:
    reason = f"{row.get('error_type') or ''} {row.get('error') or ''}".lower()
    if "no chunks" in reason or "no_rag_eligible_content" in reason or "average_chunk_length" in reason:
        return "Source Corpus Issues"
    if "quality gate" in reason:
        return "Pipeline Issues"
    if "artifact" in reason or "tar" in reason or "json" in reason:
        return "Artifact Issues"
    return "Publication Issues"


def grade_success(report: dict[str, Any]) -> bool:
    metrics = report.get("quality_metrics", {})
    return (
        metrics.get("tutor_quality", 0.0) > 90.0
        and metrics.get("reader_quality", 0.0) > 90.0
        and metrics.get("summary_quality", 0.0) > 80.0
        and metrics.get("quality_gate_pass_rate", 0.0) == 100.0
    )


def comparison_markdown(reports: dict[int, dict[str, Any]]) -> str:
    lines = [
        "# Multi-Grade Comparison Report",
        "",
        "| Grade | Tutor | Reader | Summary | Formula Coverage | Concept Coverage | Publication Rate | Compared With Grade 8 |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for grade in sorted(reports):
        metrics = reports[grade]["quality_metrics"]
        lines.append(
            f"| {grade} | {metrics.get('tutor_quality', 0):.2f} | {metrics.get('reader_quality', 0):.2f} | "
            f"{metrics.get('summary_quality', 0):.2f} | {metrics.get('formula_coverage', 0):.2f} | "
            f"{metrics.get('concept_coverage', 0):.2f} | {reports[grade].get('publication_rate', 0):.2f} | "
            f"Tutor {metrics.get('tutor_quality', 0) - GRADE8_BASELINE['tutor_quality']:+.2f}, "
            f"Reader {metrics.get('reader_quality', 0) - GRADE8_BASELINE['reader_quality']:+.2f}, "
            f"Summary {metrics.get('summary_quality', 0) - GRADE8_BASELINE['summary_quality']:+.2f} |"
        )
    lines.extend(
        [
            "",
            "## Grade 8 Baseline",
            "",
            "```json",
            json.dumps(GRADE8_BASELINE, indent=2, ensure_ascii=False, sort_keys=True),
            "```",
        ]
    )
    return "\n".join(lines)


def regeneration_markdown(reports: dict[int, dict[str, Any]], inventories: dict[int, dict[str, Any]]) -> str:
    any_success = any(grade_success(report) for report in reports.values())
    lines = [
        "# Multi-Grade Regeneration Report",
        "",
        f"Final verdict: {'PASS' if any_success else 'REQUIRES_ADDITIONAL_WORK'}",
        "",
        "## Summary",
        "",
        "| Grade | Targeted | Published | Rejected | Failed | Publication Rate | Grade Success |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for grade in sorted(reports):
        report = reports[grade]
        lines.append(
            f"| {grade} | {report['packs_targeted']} | {report['packs_published']} | {report['packs_rejected']} | "
            f"{report['packs_failed']} | {report['publication_rate']:.2f} | {'PASS' if grade_success(report) else 'FAIL'} |"
        )
    lines.extend(["", "## Failure Analysis", ""])
    for grade in sorted(reports):
        failures = reports[grade].get("failure_analysis", [])
        lines.extend([f"### Grade {grade}", "", "```json", json.dumps(failures, indent=2, ensure_ascii=False, sort_keys=True), "```", ""])
    lines.extend(
        [
            "## Scope",
            "",
            "Grades 6, 7, 9, and 10 were regenerated using the existing approved Grade 8 pipeline. No pipeline tuning or frontend changes were performed.",
        ]
    )
    return "\n".join(lines)


async def main_async() -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    repository = PackRepository(PACK_STORAGE_PATH)
    generator = PackGenerator(
        qdrant_url=QDRANT_URL,
        qdrant_collection=QDRANT_COLLECTION,
        pack_storage_path=str(PACK_STORAGE_PATH),
        curriculum_graph_path=CURRICULUM_GRAPH_PATH,
    )
    inventories: dict[int, dict[str, Any]] = {}
    reports: dict[int, dict[str, Any]] = {}
    for grade in GRADES:
        targets = grade_records(repository, grade)
        inventories[grade] = inventory(targets, grade)
        write_json(f"grade{grade}_pack_inventory.json", inventories[grade])
    for grade in GRADES:
        reports[grade] = await regenerate_grade(generator, grade, inventories[grade]["rows"])
        write_json(f"grade{grade}_quality_report.json", reports[grade])
    (OUT_DIR / "MULTI_GRADE_COMPARISON_REPORT.md").write_text(comparison_markdown(reports), encoding="utf-8")
    (OUT_DIR / "MULTI_GRADE_REGENERATION_REPORT.md").write_text(regeneration_markdown(reports, inventories), encoding="utf-8")
    return {"inventories": inventories, "reports": reports}


def main() -> None:
    payload = asyncio.run(main_async())
    reports = payload["reports"]
    print(
        json.dumps(
            {
                grade: {
                    "targeted": report["packs_targeted"],
                    "published": report["packs_published"],
                    "rejected": report["packs_rejected"],
                    "failed": report["packs_failed"],
                    "quality": report["quality_metrics"],
                    "grade_success": grade_success(report),
                }
                for grade, report in reports.items()
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
