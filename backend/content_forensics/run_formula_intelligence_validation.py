#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.semantic_content_pipeline import SemanticContentPipeline

from .common import qdrant_query_chunks
from .ground_truth_builder import build_ground_truth


OUT_DIR = Path("/shared/formula_intelligence")


def write_json(name: str, payload: Any) -> None:
    (OUT_DIR / name).write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def run_validation() -> dict[str, Any]:
    pipeline = SemanticContentPipeline()
    rows = []
    totals = {
        "source_formulas": 0,
        "detected_formulas": 0,
        "explained_formulas": 0,
        "coverage_weight": 0.0,
        "variable_weight": 0.0,
        "source_weight": 0,
        "gate_passed": 0,
    }
    for item in build_ground_truth():
        chunks = qdrant_query_chunks(8, item["subject"], item["chapter"])
        result = pipeline.build(chunks, pack_id=item["pack_id"], metadata={**item, "grade": 8, "language": "english"})
        formula = result.reports.get("formula_validation", {})
        source = int(formula.get("source_formulas", 0))
        totals["source_formulas"] += source
        totals["detected_formulas"] += int(formula.get("detected_formulas", 0))
        totals["explained_formulas"] += int(formula.get("explained_formulas", 0))
        totals["coverage_weight"] += float(formula.get("coverage", 0.0)) * source
        totals["variable_weight"] += float(formula.get("variable_coverage", 0.0)) * max(1, int(formula.get("detected_formulas", 0)))
        totals["source_weight"] += source
        totals["gate_passed"] += 1 if result.quality_gate.get("passed") else 0
        rows.append(
            {
                "pack_id": item["pack_id"],
                "chapter": item["chapter"],
                "subject": item["subject"],
                "formula_validation": formula,
                "quality_gate": result.quality_gate,
                "formula_artifacts": len(result.artifacts.get("formulas", [])),
            }
        )
    detected = totals["detected_formulas"]
    report = {
        "source_formulas": totals["source_formulas"],
        "detected_formulas": detected,
        "coverage": round(totals["coverage_weight"] / max(1, totals["source_weight"]), 2),
        "explained_formulas": totals["explained_formulas"],
        "formula_explanation_rate": round(100.0 * totals["explained_formulas"] / max(1, detected), 2),
        "variable_coverage": round(totals["variable_weight"] / max(1, detected), 2),
        "quality_gate_pass_rate": round(100.0 * totals["gate_passed"] / max(1, len(rows)), 2),
        "quality_gate_passed_packs": totals["gate_passed"],
        "total_packs": len(rows),
        "success_criteria": {
            "formula_coverage_95_plus": round(totals["coverage_weight"] / max(1, totals["source_weight"]), 2) >= 95.0,
            "formula_explanation_rate_95_plus": round(100.0 * totals["explained_formulas"] / max(1, detected), 2) >= 95.0,
            "all_quality_gates_pass": totals["gate_passed"] == len(rows),
        },
        "rows": rows,
    }
    return report


def markdown(report: dict[str, Any]) -> str:
    passed = all(report["success_criteria"].values())
    return "\n".join(
        [
            "# Formula Intelligence Validation Report",
            "",
            f"Verdict: {'PASS' if passed else 'REQUIRES_ADDITIONAL_WORK'}",
            "",
            "## Metrics",
            "",
            "| Metric | Score | Target | Pass |",
            "| --- | ---: | ---: | --- |",
            f"| Formula Coverage | {report['coverage']:.2f} | >= 95.00 | {'PASS' if report['success_criteria']['formula_coverage_95_plus'] else 'FAIL'} |",
            f"| Formula Explanation Rate | {report['formula_explanation_rate']:.2f} | >= 95.00 | {'PASS' if report['success_criteria']['formula_explanation_rate_95_plus'] else 'FAIL'} |",
            f"| Variable Coverage | {report['variable_coverage']:.2f} | measured | INFO |",
            f"| Quality Gate Pass Rate | {report['quality_gate_pass_rate']:.2f} | 100.00 | {'PASS' if report['success_criteria']['all_quality_gates_pass'] else 'FAIL'} |",
            "",
            "## Scope",
            "",
            "Only the existing 15 Grade 8 pilot packs were processed in memory. No full regeneration or frontend changes were made.",
        ]
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report = run_validation()
    write_json("formula_validation_report.json", report)
    (OUT_DIR / "FORMULA_INTELLIGENCE_REPORT.md").write_text(markdown(report), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("source_formulas", "detected_formulas", "coverage", "formula_explanation_rate", "quality_gate_pass_rate")}, indent=2))


if __name__ == "__main__":
    main()
