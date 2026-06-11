#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.semantic_content_pipeline import SemanticContentPipeline

from .common import percent, qdrant_query_chunks
from .ground_truth_builder import build_ground_truth
from .source_chunk_classifier import SourceChunkClassifier


OUT_DIR = Path("/shared/explanation_recovery")
BASELINE = {
    "missing_explanations": 14.15,
    "educational_density": 46.69,
    "tutor_ready": 43.18,
}


def write_json(name: str, payload: Any) -> None:
    (OUT_DIR / name).write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def classify_generated_content(content: list[dict[str, Any]]) -> dict[str, Any]:
    classifier = SourceChunkClassifier()
    rows = []
    educational = tutor_ready = 0
    for item in content:
        row = classifier.classify({"chunk_id": item.get("chunk_id"), "text": item.get("text"), "metadata": item.get("metadata", {})})
        rows.append(row)
        if row["category"] in {"CONCEPT_EXPLANATION", "DEFINITION", "WORKED_EXAMPLE", "FORMULA_EXPLANATION", "GLOSSARY", "SUMMARY"}:
            educational += 1
        if classifier.tutor_ready(row["category"], str(item.get("text") or "")):
            tutor_ready += 1
    return {
        "content_chunks": len(rows),
        "educational_chunks": educational,
        "educational_density": percent(educational, len(rows)),
        "tutor_ready_chunks": tutor_ready,
        "tutor_ready": percent(tutor_ready, len(rows)),
        "classification_rows": rows[:200],
    }


def run_pilot() -> dict[str, Any]:
    pipeline = SemanticContentPipeline()
    rows = []
    totals = {
        "chunks_examined": 0,
        "chunks_recovered": 0,
        "definition_targets": 0,
        "formula_targets": 0,
        "definition_recovered_weight": 0.0,
        "formula_recovered_weight": 0.0,
        "explanation_length_weight": 0.0,
        "educational_chunks": 0,
        "content_chunks": 0,
        "tutor_ready_chunks": 0,
    }

    for item in build_ground_truth():
        chunks = qdrant_query_chunks(8, item["subject"], item["chapter"])
        result = pipeline.build(chunks, pack_id=item["pack_id"], metadata={**item, "grade": 8, "language": "english"})
        recovery = result.reports.get("explanation_recovery", {})
        generated = classify_generated_content(result.artifacts.get("content", []))

        totals["chunks_examined"] += int(recovery.get("chunks_examined", 0))
        totals["chunks_recovered"] += int(recovery.get("chunks_recovered", 0))
        totals["definition_targets"] += int(recovery.get("definition_targets", 0))
        totals["formula_targets"] += int(recovery.get("formula_targets", 0))
        totals["definition_recovered_weight"] += float(recovery.get("definition_with_explanation_rate", 0.0)) * int(recovery.get("definition_targets", 0))
        totals["formula_recovered_weight"] += float(recovery.get("formula_with_explanation_rate", 0.0)) * int(recovery.get("formula_targets", 0))
        totals["explanation_length_weight"] += float(recovery.get("average_explanation_length", 0.0)) * int(recovery.get("chunks_recovered", 0))
        totals["educational_chunks"] += int(generated.get("educational_chunks", 0))
        totals["content_chunks"] += int(generated.get("content_chunks", 0))
        totals["tutor_ready_chunks"] += int(generated.get("tutor_ready_chunks", 0))

        rows.append(
            {
                "pack_id": item["pack_id"],
                "subject": item["subject"],
                "chapter": item["chapter"],
                "source_chunks": len(chunks),
                "quality_gate_passed": result.quality_gate.get("passed"),
                "quality_gate_failures": result.quality_gate.get("failures"),
                "recovery": recovery,
                "generated_content": {
                    key: value for key, value in generated.items() if key != "classification_rows"
                },
            }
        )

    missing_rate = round(100.0 - percent(totals["chunks_recovered"], totals["chunks_examined"]), 2)
    aggregate = {
        "baseline": BASELINE,
        "chunks_examined": totals["chunks_examined"],
        "chunks_recovered": totals["chunks_recovered"],
        "missing_explanations_after": missing_rate,
        "average_explanation_length": round(totals["explanation_length_weight"] / max(1, totals["chunks_recovered"]), 2),
        "definition_with_explanation_rate": round(totals["definition_recovered_weight"] / max(1, totals["definition_targets"]), 2),
        "formula_with_explanation_rate": round(totals["formula_recovered_weight"] / max(1, totals["formula_targets"]), 2),
        "educational_density_after": percent(totals["educational_chunks"], totals["content_chunks"]),
        "tutor_ready_after": percent(totals["tutor_ready_chunks"], totals["content_chunks"]),
        "success_criteria": {
            "missing_explanations_below_5": missing_rate < 5.0,
            "educational_density_60_plus": percent(totals["educational_chunks"], totals["content_chunks"]) >= 60.0,
            "tutor_ready_60_plus": percent(totals["tutor_ready_chunks"], totals["content_chunks"]) >= 60.0,
        },
        "rows": rows,
    }
    return aggregate


def markdown(report: dict[str, Any]) -> str:
    passed = all(report["success_criteria"].values())
    return "\n".join(
        [
            "# Explanation Recovery Pilot Report",
            "",
            f"Verdict: {'PASS' if passed else 'PASS_WITH_WARNINGS' if report['chunks_recovered'] else 'FAIL'}",
            "",
            "## Metrics",
            "",
            "| Metric | Baseline | After Recovery | Target | Pass |",
            "| --- | ---: | ---: | ---: | --- |",
            f"| Missing explanations | {BASELINE['missing_explanations']:.2f}% | {report['missing_explanations_after']:.2f}% | < 5.00% | {'PASS' if report['success_criteria']['missing_explanations_below_5'] else 'FAIL'} |",
            f"| Educational density | {BASELINE['educational_density']:.2f}% | {report['educational_density_after']:.2f}% | >= 60.00% | {'PASS' if report['success_criteria']['educational_density_60_plus'] else 'FAIL'} |",
            f"| Tutor ready | {BASELINE['tutor_ready']:.2f}% | {report['tutor_ready_after']:.2f}% | >= 60.00% | {'PASS' if report['success_criteria']['tutor_ready_60_plus'] else 'FAIL'} |",
            "",
            "## Recovery",
            "",
            f"- Chunks examined: {report['chunks_examined']}",
            f"- Chunks recovered: {report['chunks_recovered']}",
            f"- Average explanation length: {report['average_explanation_length']} words",
            f"- Definition with explanation rate: {report['definition_with_explanation_rate']}%",
            f"- Formula with explanation rate: {report['formula_with_explanation_rate']}%",
            "",
            "## Scope",
            "",
            "Only the existing 15 Grade 8 pilot packs were processed in memory. No packs were published or regenerated.",
        ]
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report = run_pilot()
    write_json("explanation_recovery_report.json", report)
    (OUT_DIR / "EXPLANATION_RECOVERY_PILOT_REPORT.md").write_text(markdown(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "output_dir": str(OUT_DIR),
                "chunks_examined": report["chunks_examined"],
                "chunks_recovered": report["chunks_recovered"],
                "missing_explanations_after": report["missing_explanations_after"],
                "educational_density_after": report["educational_density_after"],
                "tutor_ready_after": report["tutor_ready_after"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
