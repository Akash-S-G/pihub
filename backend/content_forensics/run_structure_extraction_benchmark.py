#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from app.educational import (
    ConceptGraphBuilder,
    ConceptType,
    EducationalConcept,
    EducationalConceptExtractor,
    EducationalConceptValidator,
    EducationalStructureParser,
    LearningObjectiveExtractor,
)
from app.semantic_content_pipeline import SemanticContentPipeline

from .common import concept_present, percent, qdrant_query_chunks
from .ground_truth_builder import build_ground_truth
from .run_concept_precision_recovery import educational_ground_truth_terms


OUT_DIR = Path("/shared/structure_extraction")
OLD_BASELINE = {"precision": 41.13, "recall": 77.37, "f1": 53.71, "formula_coverage": 75.89}


def stable_id(name: str) -> str:
    return hashlib.sha256(re.sub(r"\s+", " ", name.lower()).strip().encode("utf-8")).hexdigest()[:16]


def write_json(name: str, payload: Any) -> None:
    (OUT_DIR / name).write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def structure_rows(ground_truth: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pipeline = SemanticContentPipeline()
    parser = EducationalStructureParser()
    old_extractor = EducationalConceptExtractor()
    rows = []
    for item in ground_truth:
        retrieved = qdrant_query_chunks(8, item["subject"], item["chapter"])
        classified, _classification, _cleanup = pipeline._classify_and_clean(retrieved)
        deduped, _dedupe = pipeline._deduplicate(classified)
        old_concepts = old_extractor.extract(deduped, item)
        structures = parser.parse(deduped, item)
        new_concepts = concepts_from_structures(structures, item, old_concepts[:20])
        rows.append(
            {
                "ground_truth": item,
                "deduped": deduped,
                "structures": structures,
                "new_concepts": new_concepts,
                "old_concepts": old_concepts,
            }
        )
    return rows


def concepts_from_structures(
    structures: dict[str, list[dict[str, Any]]],
    metadata: dict[str, Any],
    frequency_concepts: list[EducationalConcept] | None = None,
) -> list[EducationalConcept]:
    validator = EducationalConceptValidator()
    buckets: dict[str, dict[str, Any]] = {}

    def add(name: str, source_type: str, item: dict[str, Any], concept_type: ConceptType | None = None, formula: str = "", definition: str = "") -> None:
        name = clean_name(name)
        if not name:
            return
        evidence = {
            "frequency": 3,
            "has_definition": bool(definition or item.get("definition")),
            "has_formula": bool(formula),
            "has_example": source_type in {"example", "worked_example"},
            "text": " ".join(str(value) for value in (item.get("text"), definition, formula) if value),
        }
        validation = validator.validate(name, evidence)
        if not validation.valid:
            return
        key = name.lower()
        bucket = buckets.setdefault(
            key,
            {
                "name": name.title(),
                "source_types": Counter(),
                "definitions": [],
                "examples": [],
                "worked_examples": [],
                "formulas": [],
                "objectives": [],
                "chunk_ids": [],
                "concept_type": concept_type or validation.concept_type,
                "metadata": item.get("metadata") if isinstance(item.get("metadata"), dict) else metadata,
            },
        )
        bucket["source_types"][source_type] += 1
        if item.get("chunk_id") and item.get("chunk_id") not in bucket["chunk_ids"]:
            bucket["chunk_ids"].append(str(item.get("chunk_id")))
        if definition or item.get("definition"):
            append_unique(bucket["definitions"], definition or str(item.get("definition")))
        if formula:
            append_unique(bucket["formulas"], formula)
        if source_type == "example":
            append_unique(bucket["examples"], str(item.get("text") or "")[:900])
        if source_type == "worked_example":
            append_unique(bucket["worked_examples"], str(item.get("text") or "")[:1000])
        if source_type == "learning_objective":
            append_unique(bucket["objectives"], str(item.get("text") or "")[:260])

    for item in structures.get("definitions", []):
        add(str(item.get("term") or ""), "definition", item, ConceptType.DEFINITION, definition=str(item.get("definition") or ""))
    for item in structures.get("glossary", []):
        add(str(item.get("term") or ""), "glossary", item, ConceptType.DEFINITION, definition=str(item.get("definition") or ""))
    for item in structures.get("formulas", []):
        formula = str(item.get("text") or "")
        add(str(item.get("term") or formula), "formula", item, ConceptType.FORMULA, formula=formula)
    for item in structures.get("headings", []):
        add(str(item.get("term") or item.get("text") or ""), "heading", item, ConceptType.CONCEPT)
    for item in structures.get("learning_objectives", []):
        for term in terms_from_text(str(item.get("text") or ""))[:4]:
            add(term, "learning_objective", item, ConceptType.CONCEPT)
    for source_type in ("examples", "worked_examples", "summary_sections"):
        mapped_source = source_type[:-1] if source_type.endswith("s") else source_type
        for item in structures.get(source_type, []):
            for term in terms_from_text(str(item.get("text") or ""))[:3]:
                add(term, mapped_source, item, ConceptType.EXAMPLE if "example" in mapped_source else ConceptType.CONCEPT)

    concept_names = [bucket["name"] for bucket in buckets.values()]
    objectives = LearningObjectiveExtractor().extract(structures, concept_names)
    objective_map: dict[str, list[str]] = defaultdict(list)
    for objective in objectives:
        for concept in objective.get("related_concepts", []):
            objective_map[concept.lower()].append(str(objective.get("objective") or ""))

    concepts: list[EducationalConcept] = []
    for bucket in buckets.values():
        source_type = bucket["source_types"].most_common(1)[0][0] if bucket["source_types"] else "frequency_extractor"
        objectives_for_concept = bucket["objectives"] or objective_map.get(bucket["name"].lower()) or [f"Understand {bucket['name']} in this chapter."]
        concepts.append(
            EducationalConcept(
                concept_id=f"concept_{stable_id(bucket['name'])}",
                name=bucket["name"],
                concept_type=bucket["concept_type"],
                source_type=source_type,
                definition=bucket["definitions"][0] if bucket["definitions"] else f"{bucket['name']} is an important idea in this chapter.",
                examples=bucket["examples"][:3],
                worked_examples=bucket["worked_examples"][:3],
                formulas=bucket["formulas"][:6],
                learning_objectives=objectives_for_concept[:4],
                related_concepts=[],
                source_chunk_ids=bucket["chunk_ids"][:20],
                metadata=bucket["metadata"],
            )
        )
    seen_names = {concept.name.lower() for concept in concepts}
    for concept in frequency_concepts or []:
        if len(concepts) >= 45:
            break
        key = concept.name.lower()
        if key in seen_names:
            continue
        concepts.append(
            EducationalConcept(
                concept_id=concept.concept_id,
                name=concept.name,
                concept_type=concept.concept_type,
                source_type="frequency_extractor",
                definition=concept.definition,
                examples=concept.examples,
                worked_examples=concept.worked_examples,
                formulas=concept.formulas,
                learning_objectives=concept.learning_objectives,
                common_misconceptions=concept.common_misconceptions,
                prerequisites=concept.prerequisites,
                related_concepts=concept.related_concepts,
                source_chunk_ids=concept.source_chunk_ids,
                metadata=concept.metadata,
            )
        )
        seen_names.add(key)
    concepts.sort(key=lambda concept: (source_rank(concept.source_type), len(concept.formulas), len(concept.source_chunk_ids)), reverse=True)
    return concepts[:45]


def clean_name(value: str) -> str:
    value = re.sub(r"chapter\s+\d+\s*", "", value, flags=re.I)
    value = re.sub(r"^\d+(?:\.\d+)*\s*", "", value)
    value = re.sub(r"[^A-Za-z0-9\s-]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:70]


def terms_from_text(text: str) -> list[str]:
    candidates = []
    for match in re.finditer(r"\b([A-Za-z]{4,}(?:\s+(?:of|and|in|to|with|[A-Za-z]{4,})){0,3})\b", text):
        phrase = clean_name(match.group(1))
        tokens = phrase.lower().split()
        if 1 <= len(tokens) <= 4 and not tokens[0] in {"this", "that", "these", "those", "which", "where", "there", "their"}:
            candidates.append(phrase)
    return list(dict.fromkeys(candidates))


def source_rank(source_type: str) -> int:
    return {
        "definition": 7,
        "glossary": 6,
        "formula": 6,
        "heading": 5,
        "learning_objective": 4,
        "worked_example": 3,
        "example": 2,
        "frequency_extractor": 1,
    }.get(source_type, 0)


def append_unique(items: list[str], value: str) -> None:
    value = re.sub(r"\s+", " ", str(value or "")).strip()
    if value and value not in items:
        items.append(value)


def benchmark(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    output_rows = []
    total_tp = total_extracted = total_gt = total_recalled = 0
    for row in rows:
        gt = educational_ground_truth_terms(row["ground_truth"])
        concepts = [concept.name for concept in row[key]]
        tp = sum(1 for concept in concepts if concept_present(concept, gt))
        recalled = sum(1 for concept in gt if concept_present(concept, concepts))
        precision = percent(tp, len(concepts))
        recall = percent(recalled, len(gt))
        f1 = round((2 * precision * recall / (precision + recall)) if precision + recall else 0.0, 2)
        total_tp += tp
        total_extracted += len(concepts)
        total_gt += len(gt)
        total_recalled += recalled
        output_rows.append(
            {
                "pack_id": row["ground_truth"]["pack_id"],
                "chapter": row["ground_truth"]["chapter"],
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "ground_truth_count": len(gt),
                "extracted_count": len(concepts),
                "missing_concepts": [concept for concept in gt if not concept_present(concept, concepts)][:40],
                "false_positive_candidates": [concept for concept in concepts if not concept_present(concept, gt)][:40],
            }
        )
    precision = percent(total_tp, total_extracted)
    recall = percent(total_recalled, total_gt)
    f1 = round((2 * precision * recall / (precision + recall)) if precision + recall else 0.0, 2)
    return {"precision": precision, "recall": recall, "f1": f1, "rows": output_rows}


def structure_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    report_rows = []
    totals = Counter()
    for row in rows:
        counts = {key: len(value) for key, value in row["structures"].items()}
        totals.update(counts)
        report_rows.append({"pack_id": row["ground_truth"]["pack_id"], "chapter": row["ground_truth"]["chapter"], **counts})
    return {"totals": dict(totals), "packs": report_rows}


def source_precision_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    buckets: dict[str, dict[str, int]] = defaultdict(lambda: {"tp": 0, "count": 0})
    for row in rows:
        gt = educational_ground_truth_terms(row["ground_truth"])
        for concept in row["new_concepts"]:
            source = concept.source_type
            buckets[source]["count"] += 1
            if concept_present(concept.name, gt):
                buckets[source]["tp"] += 1
    metrics = {}
    for source, values in sorted(buckets.items()):
        metrics[f"{source}_precision"] = percent(values["tp"], values["count"])
        metrics[f"{source}_count"] = values["count"]
    return metrics


def formula_v2_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    output_rows = []
    total_source = total_retained = 0
    for row in rows:
        source_formulas = row["ground_truth"].get("formulae", [])
        extracted_formulas = [formula for concept in row["new_concepts"] for formula in concept.formulas]
        retained = sum(1 for formula in source_formulas if concept_present(formula, extracted_formulas))
        total_source += len(source_formulas)
        total_retained += retained
        output_rows.append(
            {
                "pack_id": row["ground_truth"]["pack_id"],
                "chapter": row["ground_truth"]["chapter"],
                "source_formulas": len(source_formulas),
                "extracted_formulas": len(extracted_formulas),
                "coverage_percent": percent(retained, len(source_formulas)),
                "missing_formulas": [formula for formula in source_formulas if not concept_present(formula, extracted_formulas)][:40],
            }
        )
    return {"formula_coverage": percent(total_retained, total_source), "rows": output_rows}


def graph_v2(rows: list[dict[str, Any]]) -> dict[str, Any]:
    builder = ConceptGraphBuilder()
    return {
        "packs": [
            {
                "pack_id": row["ground_truth"]["pack_id"],
                "chapter": row["ground_truth"]["chapter"],
                "graph": builder.build(row["new_concepts"]),
            }
            for row in rows
        ]
    }


def objectives_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    extractor = LearningObjectiveExtractor()
    report_rows = []
    for row in rows:
        concept_names = [concept.name for concept in row["new_concepts"]]
        objectives = extractor.extract(row["structures"], concept_names)
        report_rows.append({"pack_id": row["ground_truth"]["pack_id"], "chapter": row["ground_truth"]["chapter"], "objectives": objectives, "count": len(objectives)})
    return {"packs": report_rows, "total_objectives": sum(row["count"] for row in report_rows)}


def comparison_report(old: dict[str, Any], new: dict[str, Any], formula_report: dict[str, Any]) -> dict[str, Any]:
    return {
        "old_precision": old["precision"],
        "new_precision": new["precision"],
        "old_recall": old["recall"],
        "new_recall": new["recall"],
        "old_f1": old["f1"],
        "new_f1": new["f1"],
        "old_formula_coverage": old["formula_coverage"],
        "new_formula_coverage": formula_report["formula_coverage"],
        "rows": new["rows"],
    }


def markdown(comparison: dict[str, Any]) -> str:
    approved = (
        comparison["new_precision"] >= 70
        and comparison["new_recall"] >= 85
        and comparison["new_f1"] >= 75
        and comparison["new_formula_coverage"] >= 95
    )
    return "\n".join(
        [
            "# Educational Structure Extraction Report",
            "",
            f"Verdict: {'APPROVED_FOR_GRADE8_REGENERATION' if approved else 'REQUIRES_ADDITIONAL_STRUCTURE_WORK'}",
            "",
            "## Metrics",
            "",
            "| Metric | Old | New | Required | Pass |",
            "| --- | ---: | ---: | ---: | --- |",
            f"| Precision | {comparison['old_precision']:.2f} | {comparison['new_precision']:.2f} | 70.00 | {'PASS' if comparison['new_precision'] >= 70 else 'FAIL'} |",
            f"| Recall | {comparison['old_recall']:.2f} | {comparison['new_recall']:.2f} | 85.00 | {'PASS' if comparison['new_recall'] >= 85 else 'FAIL'} |",
            f"| F1 | {comparison['old_f1']:.2f} | {comparison['new_f1']:.2f} | 75.00 | {'PASS' if comparison['new_f1'] >= 75 else 'FAIL'} |",
            f"| Formula Coverage | {comparison['old_formula_coverage']:.2f} | {comparison['new_formula_coverage']:.2f} | 95.00 | {'PASS' if comparison['new_formula_coverage'] >= 95 else 'FAIL'} |",
            "",
            "## Scope",
            "",
            "Existing 15-pack Grade 8 pilot only. No Grade 8 regeneration was performed.",
            "",
            "## Pipeline Boundaries",
            "",
            "Frontend, pack installation, RAG ingestion, curriculum layer, discovery, and sync were not modified.",
        ]
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ground_truth = build_ground_truth()
    rows = structure_rows(ground_truth)
    new_benchmark = benchmark(rows, "new_concepts")
    formula_report = formula_v2_report(rows)
    comparison = comparison_report(OLD_BASELINE, new_benchmark, formula_report)

    write_json("structure_parser_report.json", structure_report(rows))
    write_json("concept_source_precision_report.json", source_precision_report(rows))
    write_json("formula_extraction_v2_report.json", formula_report)
    write_json("concept_graph_v2.json", graph_v2(rows))
    write_json("learning_objectives_report.json", objectives_report(rows))
    write_json("concept_extractor_comparison.json", comparison)
    (OUT_DIR / "EDUCATIONAL_STRUCTURE_EXTRACTION_REPORT.md").write_text(markdown(comparison), encoding="utf-8")
    print(json.dumps({"output_dir": str(OUT_DIR), "new_precision": comparison["new_precision"], "new_recall": comparison["new_recall"], "new_f1": comparison["new_f1"]}, indent=2))


if __name__ == "__main__":
    main()
