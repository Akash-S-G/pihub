#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from app.semantic_content_pipeline import SemanticContentPipeline, normalize_text, token_set, word_count

from .common import qdrant_query_chunks
from .ground_truth_builder import build_ground_truth


OUT_DIR = Path("/shared/tutor_context_enrichment")

BENCHMARK_PROMPTS = [
    "What is this concept?",
    "Why do we learn this?",
    "How does this connect to other topics?",
    "What should I know before learning this?",
    "What mistakes do students usually make?",
    "Where is this used in real life?",
]


def write_json(name: str, payload: Any) -> None:
    (OUT_DIR / name).write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def run_validation() -> dict[str, Any]:
    pipeline = SemanticContentPipeline()
    rows = []
    totals = Counter()
    relationship_edges: dict[tuple[str, str], int] = defaultdict(int)
    misconceptions = []

    for item in build_ground_truth():
        chunks = qdrant_query_chunks(8, item["subject"], item["chapter"])
        result = pipeline.build(chunks, pack_id=item["pack_id"], metadata={**item, "grade": 8, "language": "english"})
        tutor_context = result.reports.get("tutor_context_enrichment", {})
        quality = tutor_quality(result.artifacts)
        gate_passed = bool(result.quality_gate.get("passed"))

        totals["packs"] += 1
        totals["gate_passed"] += 1 if gate_passed else 0
        totals["tutor_quality_weight"] += quality["tutor_quality_score"]
        totals["question_count"] += quality["question_count"]
        totals["answered_questions"] += quality["answered_questions"]

        graph = tutor_context.get("concept_relationship_graph", {})
        for edge in graph.get("edges") or []:
            source = str(edge.get("source") or "")
            target = str(edge.get("target") or "")
            if source and target:
                relationship_edges[(source, target)] += 1
        misconceptions.extend(tutor_context.get("misconceptions") or [])

        rows.append(
            {
                "pack_id": item["pack_id"],
                "subject": item["subject"],
                "chapter": item["chapter"],
                "tutor_context": {
                    key: tutor_context.get(key)
                    for key in (
                        "concepts_examined",
                        "concepts_enriched",
                        "tutor_context_rows_created",
                        "prerequisite_coverage_percent",
                        "related_concept_coverage_percent",
                        "misconception_coverage_percent",
                        "why_it_matters_coverage_percent",
                        "real_world_application_coverage_percent",
                        "formula_context_count",
                    )
                },
                "tutor_quality": quality,
                "quality_gate": result.quality_gate,
            }
        )

    total_packs = max(1, totals["packs"])
    aggregate_quality = round(float(totals["tutor_quality_weight"]) / total_packs, 2)
    gate_rate = round(100.0 * totals["gate_passed"] / total_packs, 2)
    report = {
        "scope": "15 Grade 8 pilot packs only",
        "packs_evaluated": totals["packs"],
        "tutor_quality": aggregate_quality,
        "quality_gate_pass_rate": gate_rate,
        "answered_question_rate": round(100.0 * totals["answered_questions"] / max(1, totals["question_count"]), 2),
        "success_criteria": {
            "tutor_quality_gt_85": aggregate_quality > 85.0,
            "quality_gate_pass_rate_gt_90": gate_rate > 90.0,
        },
        "rows": rows,
    }
    relationship_graph = {
        "nodes": sorted({source for source, _target in relationship_edges} | {target for _source, target in relationship_edges})[:500],
        "edges": [
            {"source": source, "target": target, "count": count}
            for (source, target), count in sorted(relationship_edges.items(), key=lambda item: (-item[1], item[0]))[:1000]
        ],
    }
    misconception_report = {
        "misconception_count": len(misconceptions),
        "unique_misconceptions": sorted({str(item.get("misconception") or "") for item in misconceptions if isinstance(item, dict) and item.get("misconception")})[:500],
        "rows": misconceptions[:1000],
    }
    return {
        "validation": report,
        "context_report": tutor_context_summary(rows),
        "relationship_graph": relationship_graph,
        "misconception_report": misconception_report,
    }


def tutor_context_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {}
    keys = (
        "concepts_examined",
        "concepts_enriched",
        "tutor_context_rows_created",
        "prerequisite_coverage_percent",
        "related_concept_coverage_percent",
        "misconception_coverage_percent",
        "why_it_matters_coverage_percent",
        "real_world_application_coverage_percent",
        "formula_context_count",
    )
    return {
        "packs_evaluated": len(rows),
        "averages": {
            key: round(sum(float((row.get("tutor_context") or {}).get(key) or 0.0) for row in rows) / len(rows), 2)
            for key in keys
        },
        "rows": [
            {
                "pack_id": row["pack_id"],
                "subject": row["subject"],
                "chapter": row["chapter"],
                **(row.get("tutor_context") or {}),
            }
            for row in rows
        ],
    }


def tutor_quality(artifacts: dict[str, Any]) -> dict[str, Any]:
    content = artifacts.get("content") or []
    contexts = [
        item
        for item in content
        if isinstance(item, dict)
        and isinstance(item.get("metadata"), dict)
        and item["metadata"].get("content_type") in {"tutor_context", "concept_context", "formula_explanation", "worked_example"}
    ]
    concept_contexts = [item for item in contexts if item.get("metadata", {}).get("content_type") == "tutor_context"]
    question_rows = []
    for context in concept_contexts[:25]:
        text = str(context.get("text") or "")
        metadata = context.get("metadata") or {}
        package = metadata.get("tutor_context_package") if isinstance(metadata.get("tutor_context_package"), dict) else {}
        concept = str(metadata.get("concept_name") or package.get("concept") or "")
        for prompt in BENCHMARK_PROMPTS:
            answer_text = best_answer_text(prompt, concept, text, package)
            score = tutor_answer_score(prompt, answer_text, package)
            question_rows.append({"concept": concept, "prompt": prompt, "score": score, "answered": score >= 70.0})
    if not question_rows:
        return {
            "tutor_quality_score": 0.0,
            "question_count": 0,
            "answered_questions": 0,
            "coverage": {
                "tutor_context_rows": 0,
                "why": 0.0,
                "prerequisites": 0.0,
                "relationships": 0.0,
                "misconceptions": 0.0,
                "applications": 0.0,
            },
            "sample_questions": [],
        }
    coverage = {
        "tutor_context_rows": len(concept_contexts),
        "why": percent_count(sum(1 for item in concept_contexts if item.get("metadata", {}).get("why_it_matters")), len(concept_contexts)),
        "prerequisites": percent_count(sum(1 for item in concept_contexts if item.get("metadata", {}).get("prerequisites")), len(concept_contexts)),
        "relationships": percent_count(sum(1 for item in concept_contexts if item.get("metadata", {}).get("related_concepts")), len(concept_contexts)),
        "misconceptions": percent_count(sum(1 for item in concept_contexts if item.get("metadata", {}).get("common_misconceptions")), len(concept_contexts)),
        "applications": percent_count(sum(1 for item in concept_contexts if item.get("metadata", {}).get("real_world_applications")), len(concept_contexts)),
    }
    return {
        "tutor_quality_score": round(sum(row["score"] for row in question_rows) / len(question_rows), 2),
        "question_count": len(question_rows),
        "answered_questions": sum(1 for row in question_rows if row["answered"]),
        "coverage": coverage,
        "sample_questions": question_rows[:40],
    }


def best_answer_text(prompt: str, concept: str, context_text: str, package: dict[str, Any]) -> str:
    lowered = prompt.lower()
    if "why" in lowered:
        return str(package.get("why_it_matters") or context_text)
    if "connect" in lowered:
        values = package.get("related_concepts") or []
        return f"{concept} connects with " + ", ".join(str(item) for item in values) if values else context_text
    if "know before" in lowered:
        values = package.get("prerequisites") or []
        return f"Before learning {concept}, know " + ", ".join(str(item) for item in values) if values else context_text
    if "mistakes" in lowered:
        values = package.get("common_misconceptions") or []
        return "Common mistakes include " + "; ".join(str(item) for item in values) if values else context_text
    if "real life" in lowered or "used" in lowered:
        values = package.get("real_world_applications") or []
        return f"{concept} is used in " + ", ".join(str(item) for item in values) if values else context_text
    return str(package.get("explanation") or context_text)


def tutor_answer_score(prompt: str, answer: str, package: dict[str, Any]) -> float:
    answer_terms = token_set(answer)
    if not answer_terms:
        return 0.0
    score = 35.0
    if word_count(answer) >= 8:
        score += 15.0
    if word_count(answer) >= 18:
        score += 10.0
    lowered = prompt.lower()
    if "why" in lowered and package.get("why_it_matters"):
        score += 35.0
    elif "connect" in lowered and package.get("related_concepts"):
        score += 35.0
    elif "know before" in lowered and package.get("prerequisites"):
        score += 35.0
    elif "mistakes" in lowered and package.get("common_misconceptions"):
        score += 35.0
    elif ("real life" in lowered or "used" in lowered) and package.get("real_world_applications"):
        score += 35.0
    elif package.get("explanation"):
        score += 30.0
    if package.get("example") or package.get("worked_examples"):
        score += 5.0
    if package.get("formula_context"):
        score += 5.0
    return min(100.0, round(score, 2))


def percent_count(value: int, total: int) -> float:
    if total == 0:
        return 100.0
    return round(100.0 * value / total, 2)


def markdown(payload: dict[str, Any]) -> str:
    report = payload["validation"]
    criteria = report["success_criteria"]
    passed = criteria["tutor_quality_gt_85"] and criteria["quality_gate_pass_rate_gt_90"]
    rows = report["rows"]
    gate_failures = Counter(failure for row in rows for failure in row.get("quality_gate", {}).get("failures", []))
    return "\n".join(
        [
            "# Tutor Context Enrichment Report",
            "",
            f"Verdict: {'PASS' if passed else 'REQUIRES_ADDITIONAL_WORK'}",
            "",
            "## Metrics",
            "",
            "| Metric | Score | Target | Pass |",
            "| --- | ---: | ---: | --- |",
            f"| Tutor Quality | {report['tutor_quality']:.2f} | > 85.00 | {'PASS' if criteria['tutor_quality_gt_85'] else 'FAIL'} |",
            f"| Quality Gate Pass Rate | {report['quality_gate_pass_rate']:.2f} | > 90.00 | {'PASS' if criteria['quality_gate_pass_rate_gt_90'] else 'FAIL'} |",
            f"| Answered Question Rate | {report['answered_question_rate']:.2f} | measured | INFO |",
            "",
            "## Context Coverage",
            "",
            "```json",
            json.dumps(payload["context_report"].get("averages", {}), indent=2, ensure_ascii=False, sort_keys=True),
            "```",
            "",
            "## Remaining Quality Gate Failures",
            "",
            "```json",
            json.dumps(dict(gate_failures), indent=2, ensure_ascii=False, sort_keys=True),
            "```",
            "",
            "## Scope",
            "",
            "Only the existing 15 Grade 8 pilot packs were processed in memory. Qdrant, frontend, sync, curriculum, and full corpus regeneration were not modified.",
        ]
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = run_validation()
    write_json("tutor_context_report.json", payload["context_report"])
    write_json("tutor_quality_validation.json", payload["validation"])
    write_json("concept_relationship_graph.json", payload["relationship_graph"])
    write_json("misconception_report.json", payload["misconception_report"])
    (OUT_DIR / "TUTOR_CONTEXT_ENRICHMENT_REPORT.md").write_text(markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "tutor_quality": payload["validation"]["tutor_quality"],
                "quality_gate_pass_rate": payload["validation"]["quality_gate_pass_rate"],
                "answered_question_rate": payload["validation"]["answered_question_rate"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
