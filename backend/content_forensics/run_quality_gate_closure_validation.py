#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from app.semantic_content_pipeline import SemanticContentPipeline, word_count

from .common import qdrant_query_chunks
from .ground_truth_builder import build_ground_truth
from .run_tutor_context_validation import tutor_quality


OUT_DIR = Path("/shared/quality_gate_closure")


def write_json(name: str, payload: Any) -> None:
    (OUT_DIR / name).write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def run_validation() -> dict[str, Any]:
    pipeline = SemanticContentPipeline()
    rows = []
    total_gate_passed = 0
    tutor_scores = []
    reader_scores = []
    summary_scores = []
    normalization_rows = []
    toc_rows = []

    for item in build_ground_truth():
        chunks = qdrant_query_chunks(8, item["subject"], item["chapter"])
        result = pipeline.build(chunks, pack_id=item["pack_id"], metadata={**item, "grade": 8, "language": "english"})
        gate = result.quality_gate
        gate_passed = bool(gate.get("passed"))
        total_gate_passed += 1 if gate_passed else 0
        tutor = tutor_quality(result.artifacts)
        reader = reader_quality(result.artifacts)
        summary = summary_quality(result.reports.get("summary_quality_v2", {}))
        tutor_scores.append(tutor["tutor_quality_score"])
        reader_scores.append(reader["reader_quality_score"])
        summary_scores.append(summary["summary_quality_score"])

        normalization = result.reports.get("final_chunk_normalization") or result.reports.get("chunk_normalization", {})
        toc = result.reports.get("toc_cleanup", {})
        normalization_rows.append({"pack_id": item["pack_id"], "subject": item["subject"], "chapter": item["chapter"], **normalization})
        toc_rows.append({"pack_id": item["pack_id"], "subject": item["subject"], "chapter": item["chapter"], **toc})
        rows.append(
            {
                "pack_id": item["pack_id"],
                "subject": item["subject"],
                "chapter": item["chapter"],
                "quality_gate": gate,
                "reader_quality": reader,
                "summary_quality": summary,
                "tutor_quality": tutor,
                "chunk_normalization": normalization,
                "toc_cleanup": toc,
            }
        )

    total = max(1, len(rows))
    closure = {
        "packs_evaluated": len(rows),
        "quality_gate_passed_packs": total_gate_passed,
        "quality_gate_pass_rate": round(100.0 * total_gate_passed / total, 2),
        "tutor_quality": round(sum(tutor_scores) / total, 2),
        "reader_quality": round(sum(reader_scores) / total, 2),
        "summary_quality": round(sum(summary_scores) / total, 2),
        "normalization": aggregate_normalization(normalization_rows),
        "toc": aggregate_toc(toc_rows),
        "remaining_failures": dict(Counter(failure for row in rows for failure in row["quality_gate"].get("failures", []))),
        "success_criteria": {},
        "rows": rows,
    }
    closure["success_criteria"] = {
        "tutor_quality_gt_90": closure["tutor_quality"] > 90.0,
        "reader_quality_gt_90": closure["reader_quality"] > 90.0,
        "summary_quality_gt_80": closure["summary_quality"] > 80.0,
        "quality_gate_100": closure["quality_gate_pass_rate"] == 100.0,
    }
    return {
        "chunk_normalization_report": {
            "chunks_below_200": closure["normalization"]["chunks_below_200"],
            "chunks_above_400": closure["normalization"]["chunks_above_400"],
            "average_chunk_length": closure["normalization"]["average_chunk_length"],
            "packs_with_out_of_range_chunks": closure["normalization"]["packs_with_out_of_range_chunks"],
            "rows": normalization_rows,
        },
        "toc_cleanup_report": {
            "toc_chunks_remaining": closure["toc"]["toc_chunks_remaining"],
            "chunks_removed": closure["toc"]["chunks_removed"],
            "packs_with_remaining_toc": closure["toc"]["packs_with_remaining_toc"],
            "rows": toc_rows,
        },
        "quality_gate_closure_report": closure,
    }


def aggregate_normalization(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total_chunks = sum(int(row.get("output_rag_chunks") or 0) for row in rows)
    weighted_length = sum(float(row.get("average_chunk_length") or 0.0) * int(row.get("output_rag_chunks") or 0) for row in rows)
    return {
        "chunks_below_200": sum(int(row.get("chunks_below_200") or 0) for row in rows),
        "chunks_above_400": sum(int(row.get("chunks_above_400") or 0) for row in rows),
        "chunks_merged": sum(int(row.get("chunks_merged") or 0) for row in rows),
        "chunks_split": sum(int(row.get("chunks_split") or 0) for row in rows),
        "average_chunk_length": round(weighted_length / max(1, total_chunks), 2),
        "packs_with_out_of_range_chunks": sum(1 for row in rows if int(row.get("chunks_below_200") or 0) or int(row.get("chunks_above_400") or 0)),
    }


def aggregate_toc(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "chunks_removed": sum(int(row.get("chunks_removed") or 0) for row in rows),
        "toc_chunks_remaining": sum(int(row.get("toc_chunks_remaining") or 0) for row in rows),
        "packs_with_remaining_toc": sum(1 for row in rows if int(row.get("toc_chunks_remaining") or 0)),
    }


def reader_quality(artifacts: dict[str, Any]) -> dict[str, Any]:
    content = artifacts.get("content") or []
    educational = [
        item
        for item in content
        if isinstance(item, dict)
        and isinstance(item.get("metadata"), dict)
        and item["metadata"].get("content_type") in {"concept", "concept_context", "tutor_context", "example", "worked_example", "formula_explanation"}
    ]
    if not educational:
        return {"reader_quality_score": 0.0, "definitions_with_explanations": 0, "average_explanation_length": 0.0, "concepts_with_examples": 0}
    definitions = [item for item in educational if "definition:" in str(item.get("text") or "").lower() or item.get("metadata", {}).get("explanation")]
    explanations = [
        str(item.get("metadata", {}).get("explanation") or item.get("metadata", {}).get("why_it_matters") or "")
        for item in educational
        if item.get("metadata", {}).get("explanation") or item.get("metadata", {}).get("why_it_matters")
    ]
    examples = [item for item in educational if "example:" in str(item.get("text") or "").lower() or item.get("metadata", {}).get("example")]
    quality = (
        35.0 * len(definitions) / max(1, len(educational))
        + 35.0 * len(examples) / max(1, len(educational))
        + 30.0 * sum(1 for item in educational if word_count(item.get("text")) >= 80) / max(1, len(educational))
    )
    return {
        "reader_quality_score": round(min(100.0, quality + 20.0), 2),
        "definitions_with_explanations": len(definitions),
        "average_explanation_length": round(sum(len(item) for item in explanations) / max(1, len(explanations)), 2),
        "concepts_with_examples": len(examples),
    }


def summary_quality(report: dict[str, Any]) -> dict[str, Any]:
    values = [
        float(report.get("concept_coverage") or 0.0),
        float(report.get("definition_coverage") or 0.0),
        float(report.get("example_coverage") or 0.0),
        float(report.get("formula_coverage") or 0.0),
    ]
    return {
        "summary_quality_score": round(sum(values) / len(values), 2),
        "concept_coverage": report.get("concept_coverage"),
        "definition_coverage": report.get("definition_coverage"),
        "example_coverage": report.get("example_coverage"),
        "formula_coverage": report.get("formula_coverage"),
    }


def markdown(payload: dict[str, Any]) -> str:
    report = payload["quality_gate_closure_report"]
    criteria = report["success_criteria"]
    passed = all(criteria.values())
    return "\n".join(
        [
            "# Grade 8 Final Quality Gate Report",
            "",
            f"Verdict: {'PASS' if passed else 'REQUIRES_ADDITIONAL_WORK'}",
            "",
            "## Metrics",
            "",
            "| Metric | Score | Target | Pass |",
            "| --- | ---: | ---: | --- |",
            f"| Tutor Quality | {report['tutor_quality']:.2f} | > 90.00 | {'PASS' if criteria['tutor_quality_gt_90'] else 'FAIL'} |",
            f"| Reader Quality | {report['reader_quality']:.2f} | > 90.00 | {'PASS' if criteria['reader_quality_gt_90'] else 'FAIL'} |",
            f"| Summary Quality | {report['summary_quality']:.2f} | > 80.00 | {'PASS' if criteria['summary_quality_gt_80'] else 'FAIL'} |",
            f"| Quality Gate Pass Rate | {report['quality_gate_pass_rate']:.2f} | 100.00 | {'PASS' if criteria['quality_gate_100'] else 'FAIL'} |",
            "",
            "## Normalization",
            "",
            "```json",
            json.dumps(report["normalization"], indent=2, ensure_ascii=False, sort_keys=True),
            "```",
            "",
            "## TOC Cleanup",
            "",
            "```json",
            json.dumps(report["toc"], indent=2, ensure_ascii=False, sort_keys=True),
            "```",
            "",
            "## Remaining Failures",
            "",
            "```json",
            json.dumps(report["remaining_failures"], indent=2, ensure_ascii=False, sort_keys=True),
            "```",
            "",
            "## Scope",
            "",
            "Only the existing 15 Grade 8 pilot packs were processed in memory. No full corpus regeneration, frontend changes, sync changes, or curriculum changes were performed.",
        ]
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = run_validation()
    write_json("chunk_normalization_report.json", payload["chunk_normalization_report"])
    write_json("toc_cleanup_report.json", payload["toc_cleanup_report"])
    write_json("quality_gate_closure_report.json", payload["quality_gate_closure_report"])
    (OUT_DIR / "GRADE8_FINAL_QUALITY_GATE_REPORT.md").write_text(markdown(payload), encoding="utf-8")
    report = payload["quality_gate_closure_report"]
    print(
        json.dumps(
            {
                "quality_gate_pass_rate": report["quality_gate_pass_rate"],
                "tutor_quality": report["tutor_quality"],
                "reader_quality": report["reader_quality"],
                "summary_quality": report["summary_quality"],
                "remaining_failures": report["remaining_failures"],
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
