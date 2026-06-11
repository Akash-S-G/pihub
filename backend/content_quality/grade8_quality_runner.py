#!/usr/bin/env python3
from __future__ import annotations

import json
import statistics
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from app.semantic_content_pipeline import SemanticContentPipeline, word_count

try:
    from .flashcard_evaluator import FlashcardEvaluator
    from .quiz_evaluator import QuizEvaluator
    from .reader_evaluator import ReaderEvaluator
    from .summary_evaluator import SummaryEvaluator
    from .tutor_evaluator import TutorEvaluator
except ImportError:  # pragma: no cover - supports direct script execution in Docker.
    from content_quality.flashcard_evaluator import FlashcardEvaluator
    from content_quality.quiz_evaluator import QuizEvaluator
    from content_quality.reader_evaluator import ReaderEvaluator
    from content_quality.summary_evaluator import SummaryEvaluator
    from content_quality.tutor_evaluator import TutorEvaluator


BASE_URL = "http://localhost:8030"
GRADE = 8
OUT_DIR = Path("/shared/grade8_content_quality_recovery")


def get_json(path: str) -> Any:
    with urllib.request.urlopen(f"{BASE_URL}{path}", timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def post_json(path: str, payload: dict[str, Any]) -> tuple[int, Any]:
    request = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=900) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed: Any = json.loads(body)
        except json.JSONDecodeError:
            parsed = body
        return exc.code, parsed


def load_json(path: Path) -> Any:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def pack_dir(pack: dict[str, Any]) -> Path:
    manifest_path = pack.get("manifest_path")
    if manifest_path:
        return Path(str(manifest_path)).parent
    archive = Path(str(pack.get("archive_path") or ""))
    return archive.with_suffix("").with_suffix("")


def load_artifacts(pack: dict[str, Any]) -> dict[str, Any]:
    directory = pack_dir(pack)
    return {
        "content": load_json(directory / "content.json"),
        "concepts": load_json(directory / "concepts.json"),
        "examples": load_json(directory / "examples.json"),
        "worked_examples": load_json(directory / "worked_examples.json"),
        "activities": load_json(directory / "activities.json"),
        "questions": load_json(directory / "questions.json"),
        "glossary": load_json(directory / "glossary.json"),
        "quizzes": load_json(directory / "quizzes.json"),
        "flashcards": load_json(directory / "flashcards.json"),
        "summaries": load_json(directory / "summaries.json"),
    }


def grade8_packs() -> list[dict[str, Any]]:
    return [pack for pack in get_json("/packs/list").get("packs", []) if str(pack.get("grade")) == str(GRADE)]


def generation_payload(pack: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "pack_type": "chapter" if pack.get("chapter") else "class",
        "grade": GRADE,
        "subject": pack.get("subject"),
        "chapter": pack.get("chapter"),
        "language": pack.get("language") or "english",
    }
    return {key: value for key, value in payload.items() if value not in (None, "")}


def evaluate_all(packs: list[dict[str, Any]]) -> dict[str, Any]:
    reader = ReaderEvaluator().evaluate(packs, load_artifacts)
    summary = SummaryEvaluator().evaluate(packs, load_artifacts)
    quiz = QuizEvaluator().evaluate(packs, load_artifacts)
    flashcard = FlashcardEvaluator().evaluate(packs, load_artifacts)
    tutor = TutorEvaluator().evaluate(packs, load_artifacts)
    return {
        "reader_quality": reader["reader_quality"],
        "summary_quality": summary["summary_quality"],
        "quiz_quality": quiz["quiz_quality"],
        "flashcard_quality": flashcard["flashcard_quality"],
        "tutor_quality": tutor["tutor_quality"],
        "details": {
            "reader": reader,
            "summary": summary,
            "quiz": quiz,
            "flashcard": flashcard,
            "tutor": tutor,
        },
    }


def dedupe_analysis(packs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for pack in packs:
        report = load_json(pack_dir(pack) / "reports" / "deduplication_report.json")
        cleanup = load_json(pack_dir(pack) / "reports" / "content_cleanup_report.json")
        for item in (cleanup.get("sample_removed_chunks") if isinstance(cleanup, dict) else []) or []:
            rows.append(
                {
                    "pack_id": pack.get("pack_id"),
                    "chapter": pack.get("chapter"),
                    "chunk_id": item.get("chunk_id"),
                    "removed_reason": item.get("reason"),
                    "similarity_score": None,
                }
            )
        if isinstance(report, dict):
            rows.append(
                {
                    "pack_id": pack.get("pack_id"),
                    "chapter": pack.get("chapter"),
                    "removed_reason": "dedupe_summary",
                    "duplicates_removed": report.get("duplicates_removed", 0),
                    "duplicates_kept": report.get("duplicates_kept", 0),
                    "similarity_score": report.get("near_duplicate_threshold"),
                }
            )
    return rows


def chunking_benchmark(packs: list[dict[str, Any]]) -> dict[str, Any]:
    profiles = {
        "Profile A": (100, 200),
        "Profile B": (150, 300),
        "Profile C": (200, 400),
        "Profile D": (250, 500),
    }
    rows = []
    source_rows = []
    for pack in packs[:20]:
        source_rows.append((pack, load_artifacts(pack).get("content", [])))
    for name, (min_words, max_words) in profiles.items():
        pipeline = SemanticContentPipeline(min_words=min_words, max_words=max_words)
        temp_dir = OUT_DIR / "benchmark" / name.replace(" ", "_")
        temp_dir.mkdir(parents=True, exist_ok=True)
        bench_packs = []
        for pack, content in source_rows:
            result = pipeline.build(content, str(pack.get("pack_id")), pack)
            synthetic = dict(pack)
            synthetic["manifest_path"] = str(temp_dir / str(pack.get("pack_id")) / "manifest.json")
            directory = Path(synthetic["manifest_path"]).parent
            directory.mkdir(parents=True, exist_ok=True)
            for key in ("content", "concepts", "examples", "worked_examples", "activities", "questions", "glossary", "quizzes", "flashcards", "summaries"):
                (directory / f"{key}.json").write_text(json.dumps(result.artifacts.get(key, []), indent=2), encoding="utf-8")
            bench_packs.append(synthetic)
        evals = evaluate_all(bench_packs)
        rows.append(
            {
                "profile": name,
                "min_words": min_words,
                "max_words": max_words,
                "reader_quality": evals["reader_quality"],
                "tutor_accuracy": evals["tutor_quality"],
                "retrieval_precision": evals["details"]["tutor"]["metrics"]["retrieval_precision"],
                "summary_quality": evals["summary_quality"],
            }
        )
    best = max(rows, key=lambda row: (row["reader_quality"] + row["tutor_accuracy"] + row["retrieval_precision"] + row["summary_quality"]) / 4)
    return {"profiles": rows, "selected_profile": best}


def regenerate_grade8() -> dict[str, Any]:
    before = grade8_packs()
    before_scores = evaluate_all(before)
    before_content = [row for pack in before for row in load_artifacts(pack).get("content", [])]
    started = time.time()
    rows = []
    for pack in before:
        status, response = post_json("/packs/generate", generation_payload(pack))
        rows.append({"pack_id": pack.get("pack_id"), "status_code": status, "response": response, "regenerated": 200 <= int(status) < 300})
    after = grade8_packs()
    after_scores = evaluate_all(after)
    after_content = [row for pack in after for row in load_artifacts(pack).get("content", [])]
    gates = []
    for pack in after:
        gate = load_json(pack_dir(pack) / "reports" / "quality_gate.json")
        if isinstance(gate, dict):
            gates.append(gate)
    return {
        "grade": GRADE,
        "packs_targeted": len(before),
        "packs_regenerated": sum(1 for row in rows if row["regenerated"]),
        "packs_failed": sum(1 for row in rows if not row["regenerated"]),
        "chunks_before": len(before_content),
        "chunks_after": len(after_content),
        "average_chunk_length_before": round(statistics.mean([word_count(row.get("text")) for row in before_content]) if before_content else 0, 2),
        "average_chunk_length_after": round(statistics.mean([word_count(row.get("text")) for row in after_content]) if after_content else 0, 2),
        "quality_gate_pass_rate": round(sum(1 for gate in gates if gate.get("passed")) / max(1, len(after)), 4),
        "reader_before": before_scores["reader_quality"],
        "reader_after": after_scores["reader_quality"],
        "summary_before": before_scores["summary_quality"],
        "summary_after": after_scores["summary_quality"],
        "quiz_before": before_scores["quiz_quality"],
        "quiz_after": after_scores["quiz_quality"],
        "flashcard_before": before_scores["flashcard_quality"],
        "flashcard_after": after_scores["flashcard_quality"],
        "tutor_before": before_scores["tutor_quality"],
        "tutor_after": after_scores["tutor_quality"],
        "duration_ms": round((time.time() - started) * 1000, 2),
        "rows": rows,
    }


def write(name: str, payload: Any) -> None:
    (OUT_DIR / name).write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def approval_markdown(regen: dict[str, Any]) -> str:
    scores = {
        "Reader Quality": regen["reader_after"],
        "Summary Quality": regen["summary_after"],
        "Quiz Quality": regen["quiz_after"],
        "Flashcard Quality": regen["flashcard_after"],
        "Tutor Quality": regen["tutor_after"],
        "Quality Gate Pass Rate": round(regen["quality_gate_pass_rate"] * 100, 2),
    }
    approved = all(score >= 90 for score in scores.values())
    lines = [
        "# Grade 8 Content Quality Approval",
        "",
        f"Verdict: {'APPROVED_FOR_ALL_GRADES' if approved else 'REQUIRES_ADDITIONAL_PIPELINE_WORK'}",
        "",
        "| Gate | Score | Pass |",
        "| --- | ---: | --- |",
    ]
    for name, score in scores.items():
        lines.append(f"| {name} | {score:.2f} | {'PASS' if score >= 90 else 'FAIL'} |")
    lines.extend(
        [
            "",
            "## Before vs After",
            "",
            "```json",
            json.dumps({key: regen[key] for key in regen if key.endswith("_before") or key.endswith("_after") or key == "quality_gate_pass_rate"}, indent=2, sort_keys=True),
            "```",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    packs = grade8_packs()
    baseline = evaluate_all(packs)
    write(
        "grade8_quality_baseline.json",
        {
            "reader_quality": baseline["reader_quality"],
            "summary_quality": baseline["summary_quality"],
            "quiz_quality": baseline["quiz_quality"],
            "flashcard_quality": baseline["flashcard_quality"],
            "tutor_quality": baseline["tutor_quality"],
        },
    )
    write("grade8_reader_failures.json", baseline["details"]["reader"]["failures"])
    write("grade8_summary_failures.json", baseline["details"]["summary"]["failures"])
    write("grade8_quiz_failures.json", baseline["details"]["quiz"]["failures"])
    write("grade8_flashcard_failures.json", baseline["details"]["flashcard"]["failures"])
    write("grade8_tutor_benchmark.json", baseline["details"]["tutor"])
    write("grade8_deduplication_analysis.json", dedupe_analysis(packs))
    write("chunking_benchmark_report.json", chunking_benchmark(packs))
    regen = regenerate_grade8()
    write("grade8_regeneration_v2_report.json", regen)
    (OUT_DIR / "GRADE8_CONTENT_QUALITY_APPROVAL.md").write_text(approval_markdown(regen), encoding="utf-8")
    print(json.dumps({"output_dir": str(OUT_DIR), "verdict": "APPROVED_FOR_ALL_GRADES" if regen["reader_after"] >= 90 and regen["summary_after"] >= 90 and regen["quiz_after"] >= 90 and regen["flashcard_after"] >= 90 and regen["tutor_after"] >= 90 and regen["quality_gate_pass_rate"] >= 0.9 else "REQUIRES_ADDITIONAL_PIPELINE_WORK"}, indent=2))


if __name__ == "__main__":
    main()
