#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .common import percent, qdrant_query_chunks
from .ground_truth_builder import build_ground_truth
from .source_chunk_classifier import SourceChunkCategory, SourceChunkClassifier


OUT_DIR = Path("/shared/source_corpus_audit")
EDUCATIONAL_CATEGORIES = {
    SourceChunkCategory.CONCEPT_EXPLANATION.value,
    SourceChunkCategory.DEFINITION.value,
    SourceChunkCategory.WORKED_EXAMPLE.value,
    SourceChunkCategory.FORMULA_EXPLANATION.value,
    SourceChunkCategory.GLOSSARY.value,
    SourceChunkCategory.SUMMARY.value,
}
NON_EDUCATIONAL_CAUSES = {
    "Too many activities": {SourceChunkCategory.ACTIVITY.value},
    "Too many exercises": {SourceChunkCategory.EXERCISE.value, SourceChunkCategory.QUESTION.value, SourceChunkCategory.ASSESSMENT.value},
    "Too much metadata": {SourceChunkCategory.METADATA.value, SourceChunkCategory.TABLE_OF_CONTENTS.value, SourceChunkCategory.INDEX.value},
    "OCR artifacts": {SourceChunkCategory.OCR_NOISE.value},
    "Missing explanations": {SourceChunkCategory.OTHER.value},
}


def write_json(name: str, payload: Any) -> None:
    (OUT_DIR / name).write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def collect_rows(ground_truth: list[dict[str, Any]]) -> list[dict[str, Any]]:
    classifier = SourceChunkClassifier()
    rows = []
    for item in ground_truth:
        chunks = qdrant_query_chunks(8, item["subject"], item["chapter"])
        classifications = []
        for chunk in chunks:
            classified = classifier.classify(chunk)
            classified.update(
                {
                    "pack_id": item["pack_id"],
                    "pilot_subject": item["subject"],
                    "pilot_chapter": item["chapter"],
                }
            )
            classifications.append(classified)
        rows.append({"ground_truth": item, "chunks": chunks, "classifications": classifications})
    return rows


def source_chunk_classification(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [classification for row in rows for classification in row["classifications"]]


def educational_density_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    all_rows = source_chunk_classification(rows)
    educational = [row for row in all_rows if row["category"] in EDUCATIONAL_CATEGORIES]
    chapter_rows = []
    for row in rows:
        classifications = row["classifications"]
        educational_count = sum(1 for item in classifications if item["category"] in EDUCATIONAL_CATEGORIES)
        chapter_rows.append(
            {
                "pack_id": row["ground_truth"]["pack_id"],
                "chapter": row["ground_truth"]["chapter"],
                "subject": row["ground_truth"]["subject"],
                "total_chunks": len(classifications),
                "educational_chunks": educational_count,
                "educational_density_percent": percent(educational_count, len(classifications)),
                "category_counts": dict(Counter(item["category"] for item in classifications)),
            }
        )
    return {
        "total_chunks": len(all_rows),
        "educational_chunks": len(educational),
        "non_educational_chunks": len(all_rows) - len(educational),
        "educational_density_percent": percent(len(educational), len(all_rows)),
        "chapters": chapter_rows,
    }


def tutor_readiness_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    classifier = SourceChunkClassifier()
    chapter_rows = []
    total_ready = total_chunks = 0
    for row in rows:
        ready = 0
        for chunk, classified in zip(row["chunks"], row["classifications"]):
            if classifier.tutor_ready(classified["category"], str(chunk.get("text") or "")):
                ready += 1
        total_ready += ready
        total_chunks += len(row["classifications"])
        chapter_rows.append(
            {
                "pack_id": row["ground_truth"]["pack_id"],
                "chapter": row["ground_truth"]["chapter"],
                "tutor_ready_chunks": ready,
                "total_chunks": len(row["classifications"]),
                "tutor_ready_percent": percent(ready, len(row["classifications"])),
            }
        )
    return {"tutor_ready_chunks": total_ready, "total_chunks": total_chunks, "tutor_ready_percent": percent(total_ready, total_chunks), "chapters": chapter_rows}


def definition_coverage_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    chapter_rows = []
    total_present = total_expected = 0
    for row in rows:
        expected_terms = [term for term in row["ground_truth"].get("concepts", []) if len(str(term).split()) <= 4][:25]
        definition_chunks = [item for item in row["classifications"] if item["category"] in {SourceChunkCategory.DEFINITION.value, SourceChunkCategory.GLOSSARY.value}]
        definition_text = " ".join(item["preview"] for item in definition_chunks).lower()
        present = [term for term in expected_terms if str(term).lower() in definition_text]
        missing = [term for term in expected_terms if term not in present]
        total_present += len(present)
        total_expected += len(expected_terms)
        chapter_rows.append(
            {
                "pack_id": row["ground_truth"]["pack_id"],
                "chapter": row["ground_truth"]["chapter"],
                "expected_definitions": len(expected_terms),
                "definitions_present": len(present),
                "definitions_missing": len(missing),
                "coverage_percent": percent(len(present), len(expected_terms)),
                "missing_terms_sample": missing[:20],
            }
        )
    return {"definition_coverage_percent": percent(total_present, total_expected), "definitions_present": total_present, "expected_definitions": total_expected, "chapters": chapter_rows}


def worked_example_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    chapter_rows = []
    totals = Counter()
    for row in rows:
        counts = Counter(item["category"] for item in row["classifications"])
        chapter = {
            "pack_id": row["ground_truth"]["pack_id"],
            "chapter": row["ground_truth"]["chapter"],
            "worked_examples": counts[SourceChunkCategory.WORKED_EXAMPLE.value],
            "practice_problems": counts[SourceChunkCategory.EXERCISE.value] + counts[SourceChunkCategory.QUESTION.value],
            "activities": counts[SourceChunkCategory.ACTIVITY.value],
        }
        totals.update(chapter)
        chapter_rows.append(chapter)
    return {
        "worked_examples": sum(row["worked_examples"] for row in chapter_rows),
        "practice_problems": sum(row["practice_problems"] for row in chapter_rows),
        "activities": sum(row["activities"] for row in chapter_rows),
        "chapters": chapter_rows,
    }


def formula_quality_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    chapter_rows = []
    formula_chunks = explained = formula_only = 0
    for row in rows:
        chapter_formula = sum(1 for item in row["classifications"] if item["category"] in {SourceChunkCategory.FORMULA_EXPLANATION.value, SourceChunkCategory.WORKED_EXAMPLE.value})
        chapter_explained = sum(1 for item in row["classifications"] if item["category"] == SourceChunkCategory.FORMULA_EXPLANATION.value)
        chapter_formula_only = sum(1 for item in row["classifications"] if item["category"] == SourceChunkCategory.OTHER.value and re.search(r"=|≤|≥|≈|∝", item["preview"]))
        formula_chunks += chapter_formula + chapter_formula_only
        explained += chapter_explained
        formula_only += chapter_formula_only
        chapter_rows.append(
            {
                "pack_id": row["ground_truth"]["pack_id"],
                "chapter": row["ground_truth"]["chapter"],
                "formula_chunks": chapter_formula + chapter_formula_only,
                "explained_formula_chunks": chapter_explained,
                "formula_only_chunks": chapter_formula_only,
                "formula_explanation_rate": percent(chapter_explained, chapter_formula + chapter_formula_only),
            }
        )
    return {
        "formula_chunks": formula_chunks,
        "explained_formula_chunks": explained,
        "formula_only_chunks": formula_only,
        "formula_explanation_rate": percent(explained, formula_chunks),
        "chapters": chapter_rows,
    }


def chunk_quality_distribution(rows: list[dict[str, Any]]) -> dict[str, Any]:
    classifier = SourceChunkClassifier()
    counts = Counter()
    chapter_rows = []
    for row in rows:
        chapter_counts = Counter()
        for chunk, classified in zip(row["chunks"], row["classifications"]):
            label = classifier.quality_label(classified["category"], str(chunk.get("text") or ""))
            counts[label] += 1
            chapter_counts[label] += 1
        chapter_rows.append({"pack_id": row["ground_truth"]["pack_id"], "chapter": row["ground_truth"]["chapter"], "quality_counts": dict(chapter_counts)})
    total = sum(counts.values())
    return {"distribution": dict(counts), "distribution_percent": {key: percent(value, total) for key, value in counts.items()}, "chapters": chapter_rows}


def chapter_quality_ranking(rows: list[dict[str, Any]], density: dict[str, Any], tutor: dict[str, Any], definitions: dict[str, Any], formula: dict[str, Any]) -> dict[str, Any]:
    density_by_pack = {row["pack_id"]: row for row in density["chapters"]}
    tutor_by_pack = {row["pack_id"]: row for row in tutor["chapters"]}
    definition_by_pack = {row["pack_id"]: row for row in definitions["chapters"]}
    formula_by_pack = {row["pack_id"]: row for row in formula["chapters"]}
    ranking = []
    for row in rows:
        pack_id = row["ground_truth"]["pack_id"]
        educational_density = density_by_pack[pack_id]["educational_density_percent"]
        tutor_ready = tutor_by_pack[pack_id]["tutor_ready_percent"]
        definition_coverage = definition_by_pack[pack_id]["coverage_percent"]
        formula_quality = formula_by_pack[pack_id]["formula_explanation_rate"]
        overall = round((educational_density * 0.35) + (tutor_ready * 0.35) + (definition_coverage * 0.2) + (formula_quality * 0.1), 2)
        ranking.append(
            {
                "pack_id": pack_id,
                "chapter": row["ground_truth"]["chapter"],
                "subject": row["ground_truth"]["subject"],
                "educational_density": educational_density,
                "tutor_readiness": tutor_ready,
                "definition_coverage": definition_coverage,
                "formula_quality": formula_quality,
                "overall_score": overall,
            }
        )
    ranking.sort(key=lambda item: item["overall_score"], reverse=True)
    return {"chapters": ranking}


def source_corpus_root_cause(rows: list[dict[str, Any]], density: dict[str, Any], tutor: dict[str, Any]) -> dict[str, Any]:
    all_rows = source_chunk_classification(rows)
    counts = Counter(item["category"] for item in all_rows)
    causes = {}
    for cause, categories in NON_EDUCATIONAL_CAUSES.items():
        count = sum(counts[category] for category in categories)
        causes[cause] = {"chunks": count, "percent": percent(count, len(all_rows))}
    verdict = "SOURCE_CORPUS_QUALITY_IS_GOOD" if density["educational_density_percent"] >= 70 and tutor["tutor_ready_percent"] >= 65 else "SOURCE_CORPUS_QUALITY_IS_POOR"
    dominant = sorted(causes.items(), key=lambda item: item[1]["chunks"], reverse=True)
    return {
        "verdict": verdict,
        "educational_density_percent": density["educational_density_percent"],
        "tutor_ready_percent": tutor["tutor_ready_percent"],
        "category_counts": dict(counts),
        "cause_breakdown": causes,
        "dominant_causes": [{"cause": cause, **value} for cause, value in dominant],
    }


def markdown(root: dict[str, Any], density: dict[str, Any], tutor: dict[str, Any], ranking: dict[str, Any], quality: dict[str, Any]) -> str:
    answer = "YES" if root["verdict"] == "SOURCE_CORPUS_QUALITY_IS_POOR" else "NO"
    top = ranking["chapters"][:5]
    bottom = ranking["chapters"][-5:]
    lines = [
        "# Educational Source Corpus Audit",
        "",
        f"Final Answer: {answer}",
        "",
        "The educational quality problem is already present in the source corpus before generation begins."
        if answer == "YES"
        else "The source corpus is broadly educational before generation begins.",
        "",
        "## Summary",
        "",
        f"- Verdict: `{root['verdict']}`",
        f"- Total chunks: {density['total_chunks']}",
        f"- Educational density: {density['educational_density_percent']:.2f}%",
        f"- Tutor-ready chunks: {tutor['tutor_ready_percent']:.2f}%",
        f"- Educational chunks: {density['educational_chunks']}",
        f"- Non-educational chunks: {density['non_educational_chunks']}",
        "",
        "## Quality Distribution",
        "",
        "```json",
        json.dumps(quality["distribution_percent"], indent=2, sort_keys=True),
        "```",
        "",
        "## Dominant Root Causes",
        "",
        "```json",
        json.dumps(root["dominant_causes"], indent=2, sort_keys=True),
        "```",
        "",
        "## Top Chapters",
        "",
        "```json",
        json.dumps(top, indent=2, sort_keys=True),
        "```",
        "",
        "## Bottom Chapters",
        "",
        "```json",
        json.dumps(bottom, indent=2, sort_keys=True),
        "```",
        "",
        "## Scope",
        "",
        "Only the existing 15 Grade 8 pilot packs were read. Qdrant, pack generation, cleanup, deduplication, concept extraction, artifact generation, frontend, publication, and regeneration were not modified.",
    ]
    return "\n".join(lines)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ground_truth = build_ground_truth()
    rows = collect_rows(ground_truth)
    classification = source_chunk_classification(rows)
    density = educational_density_report(rows)
    tutor = tutor_readiness_report(rows)
    definitions = definition_coverage_report(rows)
    examples = worked_example_report(rows)
    formula = formula_quality_report(rows)
    quality = chunk_quality_distribution(rows)
    ranking = chapter_quality_ranking(rows, density, tutor, definitions, formula)
    root = source_corpus_root_cause(rows, density, tutor)

    write_json("source_chunk_classification.json", classification)
    write_json("educational_density_report.json", density)
    write_json("tutor_readiness_report.json", tutor)
    write_json("definition_coverage_report.json", definitions)
    write_json("worked_example_report.json", examples)
    write_json("formula_quality_report.json", formula)
    write_json("chunk_quality_distribution.json", quality)
    write_json("chapter_quality_ranking.json", ranking)
    write_json("source_corpus_root_cause.json", root)
    (OUT_DIR / "EDUCATIONAL_SOURCE_CORPUS_AUDIT.md").write_text(markdown(root, density, tutor, ranking, quality), encoding="utf-8")
    print(
        json.dumps(
            {
                "output_dir": str(OUT_DIR),
                "verdict": root["verdict"],
                "total_chunks": density["total_chunks"],
                "educational_density_percent": density["educational_density_percent"],
                "tutor_ready_percent": tutor["tutor_ready_percent"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
