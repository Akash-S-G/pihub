#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from app.semantic_content_pipeline import SemanticContentPipeline, token_set

from .common import percent, qdrant_query_chunks
from .ground_truth_builder import build_ground_truth


OUT_DIR = Path("/shared/worked_example_validation")
BENCHMARK_QUESTIONS = [
    "What is the main concept in this chapter?",
    "Explain the concept with an example.",
    "Why does the method work?",
]


def write_json(name: str, payload: Any) -> None:
    (OUT_DIR / name).write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def run_pipeline_rows() -> list[dict[str, Any]]:
    pipeline = SemanticContentPipeline()
    rows = []
    for item in build_ground_truth():
        chunks = qdrant_query_chunks(8, item["subject"], item["chapter"])
        result = pipeline.build(chunks, pack_id=item["pack_id"], metadata={**item, "grade": 8, "language": "english"})
        rows.append({"ground_truth": item, "chunks": chunks, "result": result})
    return rows


def reader_verification(rows: list[dict[str, Any]]) -> dict[str, Any]:
    report_rows = []
    total_definitions = definitions_with_explanations = concepts_with_examples = 0
    explanation_words = []
    for row in rows:
        concepts = row["result"].artifacts.get("concepts", [])
        definitions = [item for item in concepts if item.get("metadata", {}).get("key_terms")]
        explained = [item for item in concepts if item.get("metadata", {}).get("explanation")]
        with_examples = [item for item in concepts if item.get("metadata", {}).get("example")]
        explanation_words.extend(len(re.findall(r"[A-Za-z0-9]+", str(item.get("metadata", {}).get("explanation") or ""))) for item in explained)
        total_definitions += len(definitions)
        definitions_with_explanations += len(explained)
        concepts_with_examples += len(with_examples)
        score = round(
            (
                percent(len(explained), len(definitions)) * 0.5
                + percent(len(with_examples), len(concepts)) * 0.25
                + min(100.0, (sum(explanation_words[-len(explained):]) / max(1, len(explained))) / 1.2) * 0.25
            ),
            2,
        )
        report_rows.append(
            {
                "pack_id": row["ground_truth"]["pack_id"],
                "chapter": row["ground_truth"]["chapter"],
                "definitions": len(definitions),
                "definitions_with_explanations": len(explained),
                "concepts_with_examples": len(with_examples),
                "average_explanation_length": round(sum(explanation_words[-len(explained):]) / max(1, len(explained)), 2),
                "reader_quality_score": score,
            }
        )
    reader_score = round(sum(item["reader_quality_score"] for item in report_rows) / max(1, len(report_rows)), 2)
    return {
        "definitions_with_explanations": definitions_with_explanations,
        "average_explanation_length": round(sum(explanation_words) / max(1, len(explanation_words)), 2),
        "concepts_with_examples": concepts_with_examples,
        "reader_quality_score": reader_score,
        "rows": report_rows,
    }


def tutor_verification(rows: list[dict[str, Any]]) -> dict[str, Any]:
    report_rows = []
    total_score = 0.0
    for row in rows:
        content = row["result"].artifacts.get("content", [])
        chapter_terms = row["ground_truth"].get("concepts", [])[:5]
        questions = [
            *(BENCHMARK_QUESTIONS),
            *[f"What is {term}?" for term in chapter_terms[:2]],
        ]
        scores = []
        for question in questions:
            answer = best_context(question, content)
            completeness = min(100.0, len(re.findall(r"[A-Za-z0-9]+", answer)) / 1.2)
            depth = 100.0 if any(marker in answer.lower() for marker in ("because", "therefore", "hence", "explanation", "relationship", "process")) else 45.0
            example = 100.0 if any(marker in answer.lower() for marker in ("example", "problem:", "step 1", "worked")) else 35.0
            score = round(completeness * 0.35 + depth * 0.35 + example * 0.3, 2)
            scores.append({"question": question, "answer_preview": answer[:400], "answer_completeness": completeness, "explanation_depth": depth, "example_inclusion": example, "score": score})
        chapter_score = round(sum(item["score"] for item in scores) / max(1, len(scores)), 2)
        total_score += chapter_score
        report_rows.append({"pack_id": row["ground_truth"]["pack_id"], "chapter": row["ground_truth"]["chapter"], "tutor_quality": chapter_score, "questions": scores})
    return {"tutor_quality": round(total_score / max(1, len(report_rows)), 2), "rows": report_rows}


def summary_verification(rows: list[dict[str, Any]]) -> dict[str, Any]:
    report_rows = []
    total = 0.0
    for row in rows:
        summaries = row["result"].artifacts.get("summaries", [])
        summary_text = " ".join(str(item.get("text") or "") for item in summaries)
        terms = row["ground_truth"].get("concepts", [])[:15]
        covered = sum(1 for term in terms if str(term).lower() in summary_text.lower())
        explanation_retention = 100.0 if any(marker in summary_text.lower() for marker in ("definition", "worked examples", "key concepts", "key takeaways")) else 35.0
        completeness = percent(covered, len(terms))
        score = round(completeness * 0.65 + explanation_retention * 0.35, 2)
        total += score
        report_rows.append(
            {
                "pack_id": row["ground_truth"]["pack_id"],
                "chapter": row["ground_truth"]["chapter"],
                "summary_completeness": completeness,
                "concept_coverage": completeness,
                "explanation_retention": explanation_retention,
                "summary_quality": score,
            }
        )
    return {"summary_quality": round(total / max(1, len(report_rows)), 2), "rows": report_rows}


def worked_example_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    report_rows = []
    total_created = total_steps = total_concepts = total_coverage_weight = 0.0
    for row in rows:
        report = row["result"].reports.get("worked_example_builder", {})
        created = int(report.get("worked_examples_created", 0))
        total_created += created
        total_steps += float(report.get("average_steps_per_example", 0.0)) * created
        total_concepts += int(report.get("concepts_with_examples", 0))
        total_coverage_weight += float(report.get("example_coverage", 0.0))
        report_rows.append({"pack_id": row["ground_truth"]["pack_id"], "chapter": row["ground_truth"]["chapter"], **report})
    return {
        "worked_examples_created": int(total_created),
        "average_steps_per_example": round(total_steps / max(1, total_created), 2),
        "concepts_with_examples": int(total_concepts),
        "example_coverage": round(total_coverage_weight / max(1, len(report_rows)), 2),
        "rows": report_rows,
    }


def selected_pack(rows: list[dict[str, Any]], reader: dict[str, Any]) -> dict[str, Any]:
    reader_by_pack = {row["pack_id"]: row for row in reader["rows"]}
    maths_rows = [row for row in rows if row["ground_truth"].get("subject") == "maths"]
    proportional = [row for row in maths_rows if "proportion" in row["ground_truth"].get("chapter", "").lower()]
    candidates = proportional or maths_rows
    best = max(candidates, key=lambda item: reader_by_pack[item["ground_truth"]["pack_id"]]["reader_quality_score"])
    return {
        "pack_id": best["ground_truth"]["pack_id"],
        "subject": best["ground_truth"]["subject"],
        "chapter": best["ground_truth"]["chapter"],
        "reason": "proportional_reasoning_available" if proportional else "strongest_available_grade8_maths_chapter",
        "reader_quality_score": reader_by_pack[best["ground_truth"]["pack_id"]]["reader_quality_score"],
        "quality_gate": best["result"].quality_gate,
    }


def best_context(question: str, content: list[dict[str, Any]]) -> str:
    q_terms = token_set(question)
    scored = []
    for item in content:
        text = str(item.get("metadata", {}).get("tutor_context") or item.get("text") or "")
        terms = token_set(text)
        if not terms:
            continue
        overlap = len(q_terms & terms)
        score = overlap / math.sqrt(max(1, len(terms)))
        if item.get("metadata", {}).get("worked_example"):
            score += 0.15
        if item.get("metadata", {}).get("explanation"):
            score += 0.1
        scored.append((score, text))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return scored[0][1] if scored else ""


def markdown(reader: dict[str, Any], tutor: dict[str, Any], summary: dict[str, Any], worked: dict[str, Any], selected: dict[str, Any]) -> str:
    passed = (
        worked["example_coverage"] > 70
        and reader["reader_quality_score"] > 70
        and summary["summary_quality"] > 70
        and tutor["tutor_quality"] > 85
    )
    return "\n".join(
        [
            "# Worked Example Builder Report",
            "",
            f"Verdict: {'PASS' if passed else 'REQUIRES_ADDITIONAL_WORK'}",
            "",
            "## Metrics",
            "",
            "| Metric | Score | Target | Pass |",
            "| --- | ---: | ---: | --- |",
            f"| Worked Example Coverage | {worked['example_coverage']:.2f} | > 70.00 | {'PASS' if worked['example_coverage'] > 70 else 'FAIL'} |",
            f"| Reader Quality | {reader['reader_quality_score']:.2f} | > 70.00 | {'PASS' if reader['reader_quality_score'] > 70 else 'FAIL'} |",
            f"| Summary Quality | {summary['summary_quality']:.2f} | > 70.00 | {'PASS' if summary['summary_quality'] > 70 else 'FAIL'} |",
            f"| Tutor Quality | {tutor['tutor_quality']:.2f} | > 85.00 | {'PASS' if tutor['tutor_quality'] > 85 else 'FAIL'} |",
            "",
            "## Selected One-Pack Verification Candidate",
            "",
            "```json",
            json.dumps(selected, indent=2, sort_keys=True),
            "```",
            "",
            "## Scope",
            "",
            "Only the 15 Grade 8 pilot packs were processed for validation. Full regeneration was not run.",
        ]
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = run_pipeline_rows()
    reader = reader_verification(rows)
    tutor = tutor_verification(rows)
    summary = summary_verification(rows)
    worked = worked_example_report(rows)
    selected = selected_pack(rows, reader)
    write_json("reader_verification_report.json", reader)
    write_json("tutor_verification_report.json", tutor)
    write_json("summary_verification_report.json", summary)
    write_json("worked_example_report.json", worked)
    write_json("selected_pack_verification_candidate.json", selected)
    (OUT_DIR / "WORKED_EXAMPLE_BUILDER_REPORT.md").write_text(markdown(reader, tutor, summary, worked, selected), encoding="utf-8")
    print(
        json.dumps(
            {
                "output_dir": str(OUT_DIR),
                "reader_quality": reader["reader_quality_score"],
                "summary_quality": summary["summary_quality"],
                "tutor_quality": tutor["tutor_quality"],
                "worked_example_coverage": worked["example_coverage"],
                "selected_pack": selected["pack_id"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
