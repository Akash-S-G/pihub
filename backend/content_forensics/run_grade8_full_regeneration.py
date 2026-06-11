#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import tarfile
import time
from collections import Counter
from pathlib import Path
from typing import Any

from app.pack_generator import PackGenerationNoContentError, PackGenerator, PackQualityGateError
from app.pack_storage.pack_repository import PackRepository
from app.semantic_content_pipeline import word_count
from content_forensics.run_quality_gate_closure_validation import reader_quality, summary_quality
from content_forensics.run_tutor_context_validation import tutor_quality


OUT_DIR = Path("/shared/grade8_full_regeneration")
GRADE = 8
PACK_STORAGE_PATH = Path("/shared/packs")
QDRANT_URL = "http://qdrant:6333"
QDRANT_COLLECTION = "educational_chunks"
CURRICULUM_GRAPH_PATH = "/shared/work/curriculum_graph.json"

REQUIRED_ARTIFACTS = {
    "content.json": list,
    "quizzes.json": list,
    "flashcards.json": list,
    "summaries.json": list,
    "glossary.json": list,
    "enrichment.json": dict,
}

OPTIONAL_ARTIFACTS = {
    "textbook.json": (dict, list),
    "concepts.json": list,
    "examples.json": list,
    "worked_examples.json": list,
    "formulas.json": list,
    "tutor_contexts.json": list,
    "retrieval_index/index.json": dict,
    "reports/quality_gate.json": dict,
    "reports/final_chunk_normalization_report.json": dict,
    "reports/toc_cleanup_report.json": dict,
}


def write_json(name: str, payload: Any) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / name).write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def load_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def grade8_records(repository: PackRepository) -> list[dict[str, Any]]:
    records = [record for record in repository.list_packs() if str(record.get("grade")) == str(GRADE)]
    by_id = {str(record.get("pack_id")): record for record in records if record.get("pack_id")}
    return [by_id[key] for key in sorted(by_id)]


async def regenerate_record(generator: PackGenerator, record: dict[str, Any]) -> dict[str, Any]:
    pack_id = str(record.get("pack_id") or "")
    subject = str(record.get("subject") or "")
    chapter = record.get("chapter")
    language = str(record.get("language") or "english")
    before_counts = dict(record.get("artifact_counts") or {})
    started = time.time()
    try:
        if chapter:
            generated_id = await generator.generate_chapter_pack(
                grade=GRADE,
                subject=subject,
                chapter=str(chapter),
                language=language,
                compression="gzip",
                quantize_embeddings=False,
            )
        else:
            generated_id = await generator.generate_class_pack(
                grade=GRADE,
                subject=subject,
                language=language,
                include_media=False,
                compression="gzip",
                quantize_embeddings=False,
            )
        new_record = generator.repository.get_pack(generated_id) or {}
        return {
            "pack_id": pack_id,
            "generated_pack_id": generated_id,
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
            "subject": subject,
            "chapter": chapter,
            "language": language,
            "status": "rejected",
            "duration_ms": round((time.time() - started) * 1000, 2),
            "error_type": type(exc).__name__,
            "error": str(exc),
            "before_artifact_counts": before_counts,
        }
    except Exception as exc:  # pragma: no cover - operational report catches runtime faults
        return {
            "pack_id": pack_id,
            "subject": subject,
            "chapter": chapter,
            "language": language,
            "status": "failed",
            "duration_ms": round((time.time() - started) * 1000, 2),
            "error_type": type(exc).__name__,
            "error": str(exc),
            "before_artifact_counts": before_counts,
        }


def validate_artifacts(record: dict[str, Any]) -> dict[str, Any]:
    pack_dir = Path(str(record.get("pack_dir") or ""))
    archive_path = Path(str(record.get("archive_path") or ""))
    rows = []
    valid = True
    for filename, expected_type in REQUIRED_ARTIFACTS.items():
        payload = load_json(pack_dir / filename)
        exists = payload is not None
        type_ok = exists and isinstance(payload, expected_type)
        nonempty = True
        if isinstance(payload, list):
            nonempty = len(payload) > 0
        if isinstance(payload, dict):
            nonempty = len(payload) > 0
        ok = bool(exists and type_ok and nonempty)
        valid = valid and ok
        rows.append({"artifact": filename, "required": True, "exists": exists, "type_ok": type_ok, "nonempty": nonempty, "ok": ok})
    for filename, expected_type in OPTIONAL_ARTIFACTS.items():
        payload = load_json(pack_dir / filename)
        exists = payload is not None
        type_ok = not exists or isinstance(payload, expected_type)
        rows.append({"artifact": filename, "required": False, "exists": exists, "type_ok": type_ok, "nonempty": bool(payload), "ok": type_ok})

    archive = validate_archive(archive_path)
    valid = valid and archive["valid"]
    return {"valid": valid, "artifacts": rows, "archive": archive}


def validate_archive(archive_path: Path) -> dict[str, Any]:
    required = set(REQUIRED_ARTIFACTS)
    if not archive_path.exists():
        return {"valid": False, "exists": False, "missing": sorted(required), "files": []}
    try:
        with tarfile.open(archive_path, "r:gz") as archive:
            files = [member.name for member in archive.getmembers() if member.isfile()]
    except tarfile.TarError as exc:
        return {"valid": False, "exists": True, "error": str(exc), "missing": sorted(required), "files": []}
    basenames = {name.split("/", 1)[-1] for name in files}
    missing = sorted(required - basenames)
    return {
        "valid": not missing,
        "exists": True,
        "size_bytes": archive_path.stat().st_size,
        "missing": missing,
        "files": files[:80],
    }


def load_pack_artifacts(record: dict[str, Any]) -> dict[str, Any]:
    pack_dir = Path(str(record.get("pack_dir") or ""))
    return {
        "content": load_json(pack_dir / "content.json") or [],
        "summaries": load_json(pack_dir / "summaries.json") or [],
        "quizzes": load_json(pack_dir / "quizzes.json") or [],
        "flashcards": load_json(pack_dir / "flashcards.json") or [],
        "glossary": load_json(pack_dir / "glossary.json") or [],
    }


def quality_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    tutor_scores = []
    reader_scores = []
    summary_scores = []
    quiz_scores = []
    flashcard_scores = []
    gate_passes = 0
    for record in records:
        artifacts = load_pack_artifacts(record)
        synthetic_artifacts = {"content": artifacts["content"], "summaries": artifacts["summaries"]}
        tutor_scores.append(tutor_quality(synthetic_artifacts)["tutor_quality_score"])
        reader_scores.append(reader_quality(synthetic_artifacts)["reader_quality_score"])
        summary_report = load_json(Path(str(record.get("pack_dir") or "")) / "reports" / "summary_quality_v2.json") or {}
        summary_scores.append(summary_quality(summary_report)["summary_quality_score"])
        quiz_scores.append(simple_quiz_score(artifacts["quizzes"]))
        flashcard_scores.append(simple_flashcard_score(artifacts["flashcards"]))
        gate = load_json(Path(str(record.get("pack_dir") or "")) / "reports" / "quality_gate.json") or {}
        gate_passes += 1 if gate.get("passed") else 0
    total = max(1, len(records))
    return {
        "tutor_quality": average(tutor_scores),
        "reader_quality": average(reader_scores),
        "summary_quality": average(summary_scores),
        "quiz_quality": average(quiz_scores),
        "flashcard_quality": average(flashcard_scores),
        "quality_gate_pass_rate": round(100.0 * gate_passes / total, 2),
    }


def simple_quiz_score(quizzes: list[dict[str, Any]]) -> float:
    if not quizzes:
        return 0.0
    scores = []
    for quiz in quizzes:
        question = str(quiz.get("question") or "")
        answer = str(quiz.get("correct_answer") or quiz.get("answer") or "")
        explanation = str(quiz.get("explanation") or "")
        options = quiz.get("options") or []
        score = 0
        score += 25 if word_count(question) >= 3 else 0
        score += 25 if word_count(answer) >= 3 else 0
        score += 25 if word_count(explanation) >= 8 else 0
        score += 25 if isinstance(options, list) and len(options) >= 4 else 0
        scores.append(score)
    return average(scores)


def simple_flashcard_score(cards: list[dict[str, Any]]) -> float:
    if not cards:
        return 0.0
    scores = []
    for card in cards:
        front = str(card.get("front") or "")
        back = str(card.get("back") or "")
        score = 0
        score += 40 if word_count(front) >= 1 else 0
        score += 40 if word_count(back) >= 5 else 0
        score += 20 if len(back) <= 500 else 0
        scores.append(score)
    return average(scores)


def average(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


def android_validation() -> dict[str, Any]:
    adb = shutil.which("adb")
    if not adb:
        return {"status": "not_run", "reason": "adb_not_available_in_runtime_environment"}
    try:
        result = subprocess.run([adb, "devices"], check=False, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"status": "not_run", "reason": f"adb_error:{exc}"}
    devices = [
        line.split()[0]
        for line in result.stdout.splitlines()[1:]
        if line.strip() and line.split()[-1] == "device"
    ]
    if not devices:
        return {"status": "not_run", "reason": "no_android_device_detected", "adb_output": result.stdout}
    return {
        "status": "device_detected_manual_app_verification_required",
        "devices": devices,
        "checks": {
            "reader": "not_automated",
            "summary": "not_automated",
            "flashcards": "not_automated",
            "quiz": "not_automated",
            "tutor": "not_automated",
        },
    }


def markdown(report: dict[str, Any]) -> str:
    metrics = report["average_quality_metrics"]
    android = report["android_installation_validation"]
    criteria = report["success_criteria"]
    passed = all(criteria.values())
    return "\n".join(
        [
            "# Grade 8 Full Regeneration Report",
            "",
            f"Final verdict: {'PASS' if passed else 'REQUIRES_ADDITIONAL_WORK'}",
            "",
            "## Summary",
            "",
            f"- Total packs targeted: {report['total_packs_targeted']}",
            f"- Total packs regenerated: {report['total_packs_regenerated']}",
            f"- Total packs published: {report['total_packs_published']}",
            f"- Total packs rejected: {report['total_packs_rejected']}",
            f"- Total packs failed: {report['total_packs_failed']}",
            f"- Duplicate publication targets: {len(report.get('duplicate_publication_targets', []))}",
            "",
            "## Average Quality Metrics",
            "",
            "| Metric | Score | Target | Pass |",
            "| --- | ---: | ---: | --- |",
            f"| Tutor Quality | {metrics['tutor_quality']:.2f} | > 90.00 | {'PASS' if criteria['tutor_quality_gt_90'] else 'FAIL'} |",
            f"| Reader Quality | {metrics['reader_quality']:.2f} | > 90.00 | {'PASS' if criteria['reader_quality_gt_90'] else 'FAIL'} |",
            f"| Summary Quality | {metrics['summary_quality']:.2f} | > 80.00 | {'PASS' if criteria['summary_quality_gt_80'] else 'FAIL'} |",
            f"| Quality Gate Pass Rate | {metrics['quality_gate_pass_rate']:.2f} | 100.00 | {'PASS' if criteria['quality_gate_100'] else 'FAIL'} |",
            "",
            "## Artifact Validation",
            "",
            f"- Packs with valid artifacts: {report['artifact_validation']['valid_packs']}",
            f"- Packs with invalid artifacts: {report['artifact_validation']['invalid_packs']}",
            "",
            "## Duplicate Publication Targets",
            "",
            "```json",
            json.dumps(report.get("duplicate_publication_targets", []), indent=2, ensure_ascii=False, sort_keys=True),
            "```",
            "",
            "## Android Installation Validation",
            "",
            "```json",
            json.dumps(android, indent=2, ensure_ascii=False, sort_keys=True),
            "```",
            "",
            "## Notes",
            "",
            "- Regeneration used the current approved semantic pipeline exactly as wired in pack-service.",
            "- No frontend, sync, discovery, curriculum, or full-corpus changes were performed.",
        ]
    )


async def main_async() -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    started = time.time()
    repository = PackRepository(PACK_STORAGE_PATH)
    generator = PackGenerator(
        qdrant_url=QDRANT_URL,
        qdrant_collection=QDRANT_COLLECTION,
        pack_storage_path=str(PACK_STORAGE_PATH),
        curriculum_graph_path=CURRICULUM_GRAPH_PATH,
    )
    targets = grade8_records(repository)
    rows = []
    for index, record in enumerate(targets, start=1):
        print(json.dumps({"event": "GRADE8_REGENERATION_START", "index": index, "total": len(targets), "pack_id": record.get("pack_id")}))
        row = await regenerate_record(generator, record)
        print(json.dumps({"event": "GRADE8_REGENERATION_END", "pack_id": row.get("pack_id"), "status": row.get("status")}))
        rows.append(row)

    refreshed = grade8_records(generator.repository)
    published_ids = {row.get("generated_pack_id") for row in rows if row.get("status") == "published"}
    published_records = [record for record in refreshed if record.get("pack_id") in published_ids]
    metrics = quality_metrics(published_records)
    artifact_rows = [row for row in rows if row.get("status") == "published"]
    valid_artifacts = sum(1 for row in artifact_rows if row.get("artifact_validation", {}).get("valid"))
    rejected = [row for row in rows if row.get("status") == "rejected"]
    failed = [row for row in rows if row.get("status") == "failed"]
    report = {
        "grade": GRADE,
        "duration_ms": round((time.time() - started) * 1000, 2),
        "total_packs_targeted": len(targets),
        "total_packs_regenerated": len([row for row in rows if row.get("status") == "published"]),
        "total_packs_published": len(published_records),
        "total_packs_rejected": len(rejected),
        "total_packs_failed": len(failed),
        "duplicate_publication_targets": duplicate_publication_targets(rows),
        "average_quality_metrics": metrics,
        "artifact_validation": {
            "valid_packs": valid_artifacts,
            "invalid_packs": len(artifact_rows) - valid_artifacts,
        },
        "android_installation_validation": android_validation(),
        "rows": rows,
    }
    report["success_criteria"] = {
        "all_targeted_packs_published": report["total_packs_published"] == report["total_packs_targeted"] and report["total_packs_targeted"] > 0,
        "no_rejections": report["total_packs_rejected"] == 0 and report["total_packs_failed"] == 0,
        "artifact_validation_passed": report["artifact_validation"]["invalid_packs"] == 0,
        "tutor_quality_gt_90": metrics["tutor_quality"] > 90.0,
        "reader_quality_gt_90": metrics["reader_quality"] > 90.0,
        "summary_quality_gt_80": metrics["summary_quality"] > 80.0,
        "quality_gate_100": metrics["quality_gate_pass_rate"] == 100.0,
        "android_validation_executed": report["android_installation_validation"].get("status") not in {"not_run"},
    }
    write_json("grade8_regeneration_report.json", report)
    (OUT_DIR / "GRADE8_FULL_REGENERATION_REPORT.md").write_text(markdown(report), encoding="utf-8")
    return report


def main() -> None:
    report = asyncio.run(main_async())
    print(
        json.dumps(
            {
                "targeted": report["total_packs_targeted"],
                "published": report["total_packs_published"],
                "rejected": report["total_packs_rejected"],
                "failed": report["total_packs_failed"],
                "quality": report["average_quality_metrics"],
                "android": report["android_installation_validation"],
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    )


def duplicate_publication_targets(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[str]] = {}
    for row in rows:
        generated_id = row.get("generated_pack_id")
        if not generated_id:
            continue
        grouped.setdefault(str(generated_id), []).append(str(row.get("pack_id")))
    return [
        {"generated_pack_id": generated_id, "source_pack_ids": source_ids}
        for generated_id, source_ids in sorted(grouped.items())
        if len(source_ids) > 1
    ]


if __name__ == "__main__":
    main()
