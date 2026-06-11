#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from app.pack_generator import PackGenerator
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
)
from content_forensics.run_multi_grade_regeneration import (
    coverage_metrics,
    failure_record,
    grade_records,
    regenerate_record_for_grade,
)


OUT_DIR = Path("/shared/full_corpus_regeneration")
TARGET_GRADES = (1, 2, 3, 4, 5, 6, 7, 9, 10)


def write_json(name: str, payload: Any) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / name).write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def pack_inventory(records: list[dict[str, Any]], grade: int) -> dict[str, Any]:
    subject_counts = Counter(str(record.get("subject") or "unknown") for record in records)
    return {
        "grade": grade,
        "pack_count": len(records),
        "subject_count": len(subject_counts),
        "subject_counts": dict(sorted(subject_counts.items())),
        "chapter_count": len({str(record.get("chapter") or "") for record in records if record.get("chapter")}),
        "rows": [
            {
                "pack_id": record.get("pack_id"),
                "grade": grade,
                "subject": record.get("subject"),
                "chapter": record.get("chapter"),
                "language": record.get("language"),
                "artifact_counts": record.get("artifact_counts"),
            }
            for record in records
        ],
    }


async def regenerate_grade(generator: PackGenerator, grade: int, targets: list[dict[str, Any]]) -> dict[str, Any]:
    started = time.time()
    rows = []
    for index, record in enumerate(targets, start=1):
        print(
            json.dumps(
                {
                    "event": "FULL_CORPUS_REGENERATION_START",
                    "grade": grade,
                    "index": index,
                    "total": len(targets),
                    "pack_id": record.get("pack_id"),
                },
                ensure_ascii=False,
            )
        )
        row = await regenerate_record_for_grade(generator, grade, record)
        rows.append(row)
        print(
            json.dumps(
                {
                    "event": "FULL_CORPUS_REGENERATION_END",
                    "grade": grade,
                    "pack_id": row.get("pack_id"),
                    "generated_pack_id": row.get("generated_pack_id"),
                    "status": row.get("status"),
                },
                ensure_ascii=False,
            )
        )

    published_ids = {row.get("generated_pack_id") for row in rows if row.get("status") == "published"}
    refreshed = grade_records(generator.repository, grade)
    published_records = [record for record in refreshed if record.get("pack_id") in published_ids]
    rejected = [row for row in rows if row.get("status") == "rejected"]
    failed = [row for row in rows if row.get("status") == "failed"]
    metrics = quality_metrics(published_records)
    metrics.update(coverage_metrics(published_records))
    return {
        "grade": grade,
        "duration_ms": round((time.time() - started) * 1000, 2),
        "packs_targeted": len(targets),
        "packs_regenerated": sum(1 for row in rows if row.get("status") == "published"),
        "packs_published": len(published_records),
        "packs_rejected": len(rejected),
        "packs_failed": len(failed),
        "publication_rate": round(100.0 * len(published_records) / max(1, len(targets)), 2),
        "quality_metrics": metrics,
        "duplicate_publication_targets": duplicate_publication_targets(rows),
        "failure_analysis": [failure_record(row, grade) for row in [*rejected, *failed]],
        "rows": rows,
    }


def subject_statistics(grade_reports: dict[int, dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, dict[str, Any]] = defaultdict(lambda: {"targeted": 0, "published": 0, "rejected": 0, "failed": 0})
    for report in grade_reports.values():
        for row in report.get("rows", []):
            key = f"{row.get('grade')}:{row.get('subject') or 'unknown'}"
            grouped[key]["targeted"] += 1
            if row.get("status") == "published":
                grouped[key]["published"] += 1
            elif row.get("status") == "rejected":
                grouped[key]["rejected"] += 1
            elif row.get("status") == "failed":
                grouped[key]["failed"] += 1
    return dict(sorted(grouped.items()))


def aggregate_quality(grade_reports: dict[int, dict[str, Any]]) -> dict[str, Any]:
    metric_names = [
        "tutor_quality",
        "reader_quality",
        "summary_quality",
        "quiz_quality",
        "flashcard_quality",
        "quality_gate_pass_rate",
        "concept_coverage",
        "formula_coverage",
    ]
    return {
        name: average([float(report.get("quality_metrics", {}).get(name) or 0.0) for report in grade_reports.values()])
        for name in metric_names
    }


def markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Full Corpus Regeneration Report",
        "",
        f"Final verdict: {report['verdict']}",
        "",
        "## Scope",
        "",
        "- Targeted Grades: 1, 2, 3, 4, 5, 6, 7, 9, 10",
        "- Grade 8 was excluded because it was already approved as the baseline pipeline.",
        "- The runner uses the existing approved `PackGenerator` semantic pipeline without changing thresholds.",
        "",
        "## Summary",
        "",
        f"- Total packs targeted: {report['total_packs_targeted']}",
        f"- Total regenerated: {report['total_regenerated']}",
        f"- Total published: {report['total_published']}",
        f"- Total rejected: {report['total_rejected']}",
        f"- Total failed: {report['total_failed']}",
        "",
        "## Grade Statistics",
        "",
        "| Grade | Targeted | Published | Rejected | Failed | Publication Rate | Tutor | Reader | Summary | Quiz | Flashcard | Gate |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for grade in sorted(report["grade_reports"]):
        grade_report = report["grade_reports"][grade]
        metrics = grade_report.get("quality_metrics", {})
        lines.append(
            f"| {grade} | {grade_report['packs_targeted']} | {grade_report['packs_published']} | "
            f"{grade_report['packs_rejected']} | {grade_report['packs_failed']} | {grade_report['publication_rate']:.2f} | "
            f"{metrics.get('tutor_quality', 0):.2f} | {metrics.get('reader_quality', 0):.2f} | "
            f"{metrics.get('summary_quality', 0):.2f} | {metrics.get('quiz_quality', 0):.2f} | "
            f"{metrics.get('flashcard_quality', 0):.2f} | {metrics.get('quality_gate_pass_rate', 0):.2f} |"
        )
    lines.extend(
        [
            "",
            "## Subject Statistics",
            "",
            "| Grade:Subject | Targeted | Published | Rejected | Failed |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for key, stats in report["subject_statistics"].items():
        lines.append(f"| {key} | {stats['targeted']} | {stats['published']} | {stats['rejected']} | {stats['failed']} |")
    lines.extend(
        [
            "",
            "## Average Quality Metrics",
            "",
            "```json",
            json.dumps(report["average_quality_metrics"], indent=2, ensure_ascii=False, sort_keys=True),
            "```",
            "",
            "## Failure Analysis",
            "",
            "```json",
            json.dumps(report["failure_analysis"], indent=2, ensure_ascii=False, sort_keys=True)[:20000],
            "```",
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
    grade_reports: dict[int, dict[str, Any]] = {}
    for grade in TARGET_GRADES:
        records = grade_records(repository, grade)
        inventories[grade] = pack_inventory(records, grade)
        write_json(f"grade{grade}_inventory.json", inventories[grade])
    for grade in TARGET_GRADES:
        grade_reports[grade] = await regenerate_grade(generator, grade, inventories[grade]["rows"])
        write_json(f"grade{grade}_regeneration_report.json", grade_reports[grade])

    failure_analysis = [
        failure
        for grade_report in grade_reports.values()
        for failure in grade_report.get("failure_analysis", [])
    ]
    report = {
        "target_grades": TARGET_GRADES,
        "total_packs_targeted": sum(item["pack_count"] for item in inventories.values()),
        "total_regenerated": sum(item["packs_regenerated"] for item in grade_reports.values()),
        "total_published": sum(item["packs_published"] for item in grade_reports.values()),
        "total_rejected": sum(item["packs_rejected"] for item in grade_reports.values()),
        "total_failed": sum(item["packs_failed"] for item in grade_reports.values()),
        "inventories": inventories,
        "grade_reports": grade_reports,
        "subject_statistics": subject_statistics(grade_reports),
        "average_quality_metrics": aggregate_quality(grade_reports),
        "failure_analysis": failure_analysis,
    }
    report["verdict"] = "PASS" if report["total_rejected"] == 0 and report["total_failed"] == 0 else "REQUIRES_ADDITIONAL_WORK"
    write_json("full_corpus_regeneration_report.json", report)
    (OUT_DIR / "FULL_CORPUS_REGENERATION_REPORT.md").write_text(markdown(report), encoding="utf-8")
    return report


def main() -> None:
    report = asyncio.run(main_async())
    print(
        json.dumps(
            {
                "verdict": report["verdict"],
                "targeted": report["total_packs_targeted"],
                "published": report["total_published"],
                "rejected": report["total_rejected"],
                "failed": report["total_failed"],
                "average_quality_metrics": report["average_quality_metrics"],
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
