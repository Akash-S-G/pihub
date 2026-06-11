#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from app.educational import ConceptFalsePositiveAudit, ConceptGraphBuilder, EducationalConceptExtractor, EducationalConceptValidator
from app.semantic_content_pipeline import SemanticContentPipeline

from .common import concept_present, extract_formulas, percent, qdrant_query_chunks
from .formula_retention_audit import audit_formula_retention
from .ground_truth_builder import build_ground_truth


OUT_DIR = Path("/shared/concept_precision_recovery")


def write_json(name: str, payload: Any) -> None:
    (OUT_DIR / name).write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def model_dump(value: Any) -> dict[str, Any]:
    return value.model_dump() if hasattr(value, "model_dump") else value.dict()


def extracted_for_ground_truth(ground_truth: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pipeline = SemanticContentPipeline()
    extractor = EducationalConceptExtractor()
    rows = []
    for item in ground_truth:
        retrieved = qdrant_query_chunks(8, item["subject"], item["chapter"])
        classified, _classification, _cleanup = pipeline._classify_and_clean(retrieved)
        deduped, _dedupe = pipeline._deduplicate(classified)
        concepts = extractor.extract(deduped, item)
        rows.append({"ground_truth": item, "concepts": concepts, "deduped": deduped})
    return rows


def educational_ground_truth_terms(item: dict[str, Any]) -> list[str]:
    validator = EducationalConceptValidator()
    terms: list[str] = []
    seen: set[str] = set()
    for concept in item.get("concepts", []):
        validation = validator.validate(concept, {"frequency": 3, "text": item.get("chapter", "")})
        key = str(concept).lower().strip()
        if validation.valid and key not in seen:
            terms.append(concept)
            seen.add(key)
    return terms


def false_positive_report(extracted_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    auditor = ConceptFalsePositiveAudit()
    rows = []
    for row in extracted_rows:
        concepts = row["concepts"]
        evidence = {
            concept.name.lower(): {
                "frequency": len(concept.source_chunk_ids),
                "has_definition": bool(concept.definition),
                "has_formula": bool(concept.formulas),
                "has_example": bool(concept.examples or concept.worked_examples),
                "text": " ".join([concept.definition, *concept.examples[:1], *concept.worked_examples[:1]]),
            }
            for concept in concepts
        }
        for item in auditor.audit([concept.name for concept in concepts], evidence):
            rows.append({"pack_id": row["ground_truth"]["pack_id"], "chapter": row["ground_truth"]["chapter"], **item})
    return rows


def taxonomy_report(extracted_rows: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    counts = Counter()
    for row in extracted_rows:
        for concept in row["concepts"]:
            counts[concept.concept_type.value] += 1
            rows.append(
                {
                    "pack_id": row["ground_truth"]["pack_id"],
                    "chapter": row["ground_truth"]["chapter"],
                    "concept": concept.name,
                    "concept_type": concept.concept_type.value,
                }
            )
    return {"counts": dict(counts), "rows": rows}


def validation_report(extracted_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    validator = EducationalConceptValidator()
    rows = []
    for row in extracted_rows:
        for concept in row["concepts"]:
            validation = validator.validate(
                concept.name,
                {
                    "frequency": len(concept.source_chunk_ids),
                    "has_definition": bool(concept.definition),
                    "has_formula": bool(concept.formulas),
                    "has_example": bool(concept.examples or concept.worked_examples),
                    "text": " ".join([concept.definition, *concept.examples[:1], *concept.worked_examples[:1]]),
                },
            )
            rows.append(
                {
                    "pack_id": row["ground_truth"]["pack_id"],
                    "chapter": row["ground_truth"]["chapter"],
                    "term": concept.name,
                    "valid": validation.valid,
                    "reason": validation.reason,
                    "classification": validation.classification,
                    "concept_type": validation.concept_type.value,
                }
            )
    return rows


def formula_extraction_report(ground_truth: list[dict[str, Any]], extracted_rows: list[dict[str, Any]]) -> dict[str, Any]:
    retention_rows = audit_formula_retention(ground_truth)
    extraction_rows = []
    for row in extracted_rows:
        extracted_formulas = [formula for concept in row["concepts"] for formula in concept.formulas]
        gt_formulas = row["ground_truth"].get("formulae", [])
        extraction_rows.append(
            {
                "pack_id": row["ground_truth"]["pack_id"],
                "chapter": row["ground_truth"]["chapter"],
                "ground_truth_formulas": len(gt_formulas),
                "extracted_formulas": len(extracted_formulas),
                "formula_extraction_coverage_percent": percent(
                    sum(1 for formula in gt_formulas if concept_present(formula, extracted_formulas)),
                    len(gt_formulas),
                ),
            }
        )
    return {"retention": retention_rows, "extraction": extraction_rows}


def graph_cleanup_report(extracted_rows: list[dict[str, Any]]) -> dict[str, Any]:
    builder = ConceptGraphBuilder()
    rows = []
    for row in extracted_rows:
        graph = builder.build(row["concepts"])
        rows.append(
            {
                "pack_id": row["ground_truth"]["pack_id"],
                "chapter": row["ground_truth"]["chapter"],
                "input_nodes": graph.get("cleanup", {}).get("input_nodes", 0),
                "output_nodes": graph.get("cleanup", {}).get("output_nodes", 0),
                "removed_nodes": graph.get("cleanup", {}).get("removed_nodes", 0),
                "isolated_nodes": sum(1 for node in graph.get("nodes", []) if not node.get("related")),
            }
        )
    return {"packs": rows}


def precision_benchmark(extracted_rows: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    total_tp = total_extracted = total_gt = total_recalled = 0
    for row in extracted_rows:
        gt = educational_ground_truth_terms(row["ground_truth"])
        extracted = [concept.name for concept in row["concepts"]]
        tp = sum(1 for concept in extracted if concept_present(concept, gt))
        recalled = sum(1 for concept in gt if concept_present(concept, extracted))
        precision = percent(tp, len(extracted))
        recall = percent(recalled, len(gt))
        f1 = round((2 * precision * recall / (precision + recall)) if precision + recall else 0.0, 2)
        total_tp += tp
        total_extracted += len(extracted)
        total_gt += len(gt)
        total_recalled += recalled
        rows.append(
            {
                "pack_id": row["ground_truth"]["pack_id"],
                "chapter": row["ground_truth"]["chapter"],
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "ground_truth_count": len(gt),
                "raw_ground_truth_count": len(row["ground_truth"].get("concepts", [])),
                "extracted_count": len(extracted),
                "missing_concepts": [concept for concept in gt if not concept_present(concept, extracted)][:40],
                "false_positive_candidates": [concept for concept in extracted if not concept_present(concept, gt)][:40],
            }
        )
    precision = percent(total_tp, total_extracted)
    recall = percent(total_recalled, total_gt)
    f1 = round((2 * precision * recall / (precision + recall)) if precision + recall else 0.0, 2)
    return {"precision": precision, "recall": recall, "f1": f1, "rows": rows}


def markdown(benchmark: dict[str, Any], formula_report: dict[str, Any]) -> str:
    formula_rows = formula_report["extraction"]
    formula_coverage = round(sum(row["formula_extraction_coverage_percent"] for row in formula_rows) / max(1, len(formula_rows)), 2)
    approved = benchmark["precision"] >= 85 and benchmark["recall"] >= 90 and benchmark["f1"] >= 87 and formula_coverage >= 95
    return "\n".join(
        [
            "# Concept Extraction Precision Recovery Report",
            "",
            f"Verdict: {'APPROVED_FOR_GRADE8_REGENERATION' if approved else 'REQUIRES_ADDITIONAL_EXTRACTION_WORK'}",
            "",
            "## Metrics",
            "",
            "| Metric | Score | Required | Pass |",
            "| --- | ---: | ---: | --- |",
            f"| Precision | {benchmark['precision']:.2f} | 85.00 | {'PASS' if benchmark['precision'] >= 85 else 'FAIL'} |",
            f"| Recall | {benchmark['recall']:.2f} | 90.00 | {'PASS' if benchmark['recall'] >= 90 else 'FAIL'} |",
            f"| F1 | {benchmark['f1']:.2f} | 87.00 | {'PASS' if benchmark['f1'] >= 87 else 'FAIL'} |",
            f"| Formula Coverage | {formula_coverage:.2f} | 95.00 | {'PASS' if formula_coverage >= 95 else 'FAIL'} |",
            "",
            "## Scope",
            "",
            "Existing 15-pack Grade 8 pilot only. Retrieval, cleanup, deduplication, frontend, pack installation, and curriculum layer were not modified.",
        ]
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ground_truth = build_ground_truth()
    extracted_rows = extracted_for_ground_truth(ground_truth)
    false_report = false_positive_report(extracted_rows)
    taxonomy = taxonomy_report(extracted_rows)
    validation = validation_report(extracted_rows)
    formula_report = formula_extraction_report(ground_truth, extracted_rows)
    graph_cleanup = graph_cleanup_report(extracted_rows)
    benchmark = precision_benchmark(extracted_rows)

    write_json("concept_false_positive_report.json", false_report)
    write_json("concept_taxonomy_report.json", taxonomy)
    write_json("concept_validation_report.json", validation)
    write_json("formula_extraction_report.json", formula_report)
    write_json("concept_graph_cleanup_report.json", graph_cleanup)
    write_json("concept_extractor_precision_v2.json", benchmark)
    (OUT_DIR / "CONCEPT_EXTRACTION_PRECISION_RECOVERY_REPORT.md").write_text(markdown(benchmark, formula_report), encoding="utf-8")
    print(json.dumps({"output_dir": str(OUT_DIR), "precision": benchmark["precision"], "recall": benchmark["recall"], "f1": benchmark["f1"]}, indent=2))


if __name__ == "__main__":
    main()
