#!/usr/bin/env python3
from __future__ import annotations

import json
import statistics
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

try:
    from .flashcard_evaluator import FlashcardEvaluator
    from .quiz_evaluator import QuizEvaluator
    from .reader_evaluator import ReaderEvaluator
    from .summary_evaluator import SummaryEvaluator
    from .tutor_evaluator import TutorEvaluator
except ImportError:  # pragma: no cover - supports direct copied execution in Docker.
    from content_quality.flashcard_evaluator import FlashcardEvaluator
    from content_quality.quiz_evaluator import QuizEvaluator
    from content_quality.reader_evaluator import ReaderEvaluator
    from content_quality.summary_evaluator import SummaryEvaluator
    from content_quality.tutor_evaluator import TutorEvaluator


BASE_URL = "http://localhost:8030"
OUT_DIR = Path("/shared/grade8_concept_preservation")
GRADE = 8


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
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def pack_dir(pack: dict[str, Any]) -> Path:
    manifest_path = pack.get("manifest_path")
    if manifest_path:
        return Path(str(manifest_path)).parent
    archive = Path(str(pack.get("archive_path") or ""))
    return archive.with_suffix("").with_suffix("")


def load_artifacts(pack: dict[str, Any]) -> dict[str, Any]:
    directory = pack_dir(pack)
    def item(name: str) -> Any:
        value = load_json(directory / name)
        return value if isinstance(value, list) else []
    return {
        "content": item("content.json"),
        "concepts": item("concepts.json"),
        "examples": item("examples.json"),
        "worked_examples": item("worked_examples.json"),
        "glossary": item("glossary.json"),
        "quizzes": item("quizzes.json"),
        "flashcards": item("flashcards.json"),
        "summaries": item("summaries.json"),
    }


def report(pack: dict[str, Any], filename: str) -> dict[str, Any]:
    value = load_json(pack_dir(pack) / "reports" / filename)
    return value if isinstance(value, dict) else {}


def grade8_packs() -> list[dict[str, Any]]:
    return [pack for pack in get_json("/packs/list").get("packs", []) if str(pack.get("grade")) == str(GRADE)]


def subject_key(pack: dict[str, Any]) -> str:
    subject = str(pack.get("subject") or "").lower()
    if "math" in subject:
        return "maths"
    if "social" in subject:
        return "social_science"
    if "science" in subject:
        return "science"
    return subject


def select_controlled_packs(packs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    used: set[str] = set()
    for target in ("maths", "science", "social_science"):
        candidates = [
            pack for pack in packs
            if subject_key(pack) == target and pack.get("chapter") and int((pack.get("artifact_counts") or {}).get("content") or 0) > 0
        ]
        candidates.sort(key=lambda pack: str(pack.get("pack_id")))
        for pack in candidates:
            pack_id = str(pack.get("pack_id"))
            if pack_id not in used:
                selected.append(pack)
                used.add(pack_id)
            if sum(1 for item in selected if subject_key(item) == target) >= 5:
                break
    return selected


def generation_payload(pack: dict[str, Any]) -> dict[str, Any]:
    return {
        "pack_type": "chapter" if pack.get("chapter") else "class",
        "grade": GRADE,
        "subject": pack.get("subject"),
        "chapter": pack.get("chapter"),
        "language": pack.get("language") or "english",
    }


def aggregate_average(rows: list[dict[str, Any]], field: str) -> float:
    values = [float(row.get(field, 0.0) or 0.0) for row in rows]
    return round(statistics.mean(values), 2) if values else 0.0


def evaluate(selected_ids: set[str]) -> dict[str, Any]:
    packs = [pack for pack in grade8_packs() if str(pack.get("pack_id")) in selected_ids]
    return {
        "reader": ReaderEvaluator().evaluate(packs, load_artifacts),
        "summary": SummaryEvaluator().evaluate(packs, load_artifacts),
        "quiz": QuizEvaluator().evaluate(packs, load_artifacts, limit=100),
        "flashcard": FlashcardEvaluator().evaluate(packs, load_artifacts),
        "tutor": TutorEvaluator().evaluate(packs, load_artifacts),
    }


def markdown(payload: dict[str, Any]) -> str:
    scores = payload["exit_scores"]
    approved = payload["verdict"] == "APPROVED_FOR_GRADE8_REGENERATION"
    lines = [
        "# Grade 8 Concept Preservation Report",
        "",
        f"Final verdict: {'APPROVED_FOR_GRADE8_REGENERATION' if approved else 'REQUIRES_ADDITIONAL_CONCEPT_PRESERVATION_WORK'}",
        "",
        "## Scope",
        "",
        "Controlled pilot only: 5 Maths, 5 Science, 5 Social Science packs.",
        "",
        "## Exit Scores",
        "",
        "| Gate | Score | Required | Pass |",
        "| --- | ---: | ---: | --- |",
    ]
    requirements = {
        "concept_coverage": 90,
        "definition_coverage": 90,
        "formula_coverage": 95,
        "reader_quality": 70,
        "summary_quality": 70,
        "quiz_quality": 75,
        "tutor_quality": 85,
    }
    for key, required in requirements.items():
        score = float(scores.get(key, 0.0))
        lines.append(f"| {key} | {score:.2f} | {required:.2f} | {'PASS' if score >= required else 'FAIL'} |")
    lines.extend(
        [
            "",
            "## Regeneration",
            "",
            "```json",
            json.dumps(payload["regeneration"], indent=2, sort_keys=True),
            "```",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    started = time.time()
    selected = select_controlled_packs(grade8_packs())
    before_ids = {str(pack.get("pack_id")) for pack in selected}
    regen_rows = []
    response_ids: set[str] = set()

    for pack in selected:
        status, response = post_json("/packs/generate", generation_payload(pack))
        response_pack_id = response.get("pack_id") if isinstance(response, dict) else None
        if response_pack_id:
            response_ids.add(str(response_pack_id))
        regen_rows.append(
            {
                "pack_id": pack.get("pack_id"),
                "subject": pack.get("subject"),
                "chapter": pack.get("chapter"),
                "status_code": status,
                "regenerated": 200 <= int(status) < 300,
                "response": response,
            }
        )

    active_ids = before_ids | response_ids
    after_packs = [pack for pack in grade8_packs() if str(pack.get("pack_id")) in active_ids]

    concept_audits = [report(pack, "concept_audit.json") for pack in after_packs]
    concept_graphs = [report(pack, "concept_graph.json") for pack in after_packs]
    coverage_rows = [report(pack, "concept_coverage_report.json") for pack in after_packs]
    summary_rows = [report(pack, "summary_quality_v2.json") for pack in after_packs]
    quiz_rows = [report(pack, "quiz_alignment_report.json") for pack in after_packs]
    tutor_rows = [report(pack, "tutor_context_quality.json") for pack in after_packs]
    evals = evaluate({str(pack.get("pack_id")) for pack in after_packs})

    concept_graph = {
        "packs": concept_graphs,
        "concept_graph": [item for graph in concept_graphs for item in graph.get("concept_graph", [])],
        "nodes": [node for graph in concept_graphs for node in graph.get("nodes", [])],
        "edges": [edge for graph in concept_graphs for edge in graph.get("edges", [])],
    }
    coverage_report = {
        "packs": coverage_rows,
        "concept_coverage": aggregate_average(coverage_rows, "coverage_percent"),
        "definition_coverage": aggregate_average(coverage_rows, "definition_coverage_percent"),
        "example_coverage": aggregate_average(coverage_rows, "example_coverage_percent"),
        "formula_coverage": aggregate_average(coverage_rows, "formula_coverage_percent"),
        "learning_objective_coverage": aggregate_average(coverage_rows, "learning_objective_coverage_percent"),
    }
    summary_report = {"packs": summary_rows, "summary_quality": evals["summary"]["summary_quality"]}
    quiz_report = {"packs": quiz_rows, "quiz_quality": evals["quiz"]["quiz_quality"], "metrics": evals["quiz"]["metrics"]}
    tutor_report = {"packs": tutor_rows, "tutor_quality": evals["tutor"]["tutor_quality"], "metrics": evals["tutor"]["metrics"]}
    exit_scores = {
        "concept_coverage": coverage_report["concept_coverage"],
        "definition_coverage": coverage_report["definition_coverage"],
        "formula_coverage": coverage_report["formula_coverage"],
        "reader_quality": evals["reader"]["reader_quality"],
        "summary_quality": evals["summary"]["summary_quality"],
        "quiz_quality": evals["quiz"]["quiz_quality"],
        "tutor_quality": evals["tutor"]["tutor_quality"],
    }
    verdict = (
        "APPROVED_FOR_GRADE8_REGENERATION"
        if exit_scores["concept_coverage"] >= 90
        and exit_scores["definition_coverage"] >= 90
        and exit_scores["formula_coverage"] >= 95
        and exit_scores["reader_quality"] >= 70
        and exit_scores["summary_quality"] >= 70
        and exit_scores["quiz_quality"] >= 75
        and exit_scores["tutor_quality"] >= 85
        else "REQUIRES_ADDITIONAL_CONCEPT_PRESERVATION_WORK"
    )
    payload = {
        "selected_pack_count": len(selected),
        "active_pack_count": len(after_packs),
        "duration_ms": round((time.time() - started) * 1000, 2),
        "regeneration": {
            "packs_targeted": len(selected),
            "packs_regenerated": sum(1 for row in regen_rows if row["regenerated"]),
            "packs_failed": sum(1 for row in regen_rows if not row["regenerated"]),
            "rows": regen_rows,
        },
        "exit_scores": exit_scores,
        "verdict": verdict,
    }

    (OUT_DIR / "concept_audit.json").write_text(json.dumps({"packs": concept_audits}, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    (OUT_DIR / "concept_graph.json").write_text(json.dumps(concept_graph, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    (OUT_DIR / "concept_coverage_report.json").write_text(json.dumps(coverage_report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    (OUT_DIR / "summary_quality_v2.json").write_text(json.dumps(summary_report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    (OUT_DIR / "quiz_alignment_report.json").write_text(json.dumps(quiz_report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    (OUT_DIR / "tutor_context_quality.json").write_text(json.dumps(tutor_report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    (OUT_DIR / "GRADE8_CONCEPT_PRESERVATION_REPORT.md").write_text(markdown(payload), encoding="utf-8")
    print(json.dumps({"output_dir": str(OUT_DIR), "verdict": verdict, "exit_scores": exit_scores}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
