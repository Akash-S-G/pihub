#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .cleanup_loss_audit import audit_cleanup_loss
from .concept_extractor_accuracy import audit_concept_extractor
from .concept_loss_root_cause import audit_root_cause
from .deduplication_loss_audit import audit_deduplication_loss
from .formula_retention_audit import audit_formula_retention
from .ground_truth_builder import build_ground_truth
from .qdrant_retrieval_audit import audit_qdrant_retrieval


OUT_DIR = Path("/shared/grade8_content_forensics")


def write_json(name: str, payload: Any) -> None:
    (OUT_DIR / name).write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def average(rows: list[dict[str, Any]], field: str) -> float:
    values = [float(row.get(field, 0.0) or 0.0) for row in rows]
    return round(sum(values) / max(1, len(values)), 2)


def markdown(
    ground_truth: list[dict[str, Any]],
    qdrant_rows: list[dict[str, Any]],
    cleanup_rows: list[dict[str, Any]],
    dedupe_rows: list[dict[str, Any]],
    extractor_rows: list[dict[str, Any]],
    formula_rows: list[dict[str, Any]],
    root_rows: list[dict[str, Any]],
) -> str:
    counts = Counter(row["lost_at"] for row in root_rows)
    total = sum(counts.values())
    first_loss = max((stage for stage in ("retrieval", "cleanup", "deduplication", "extraction", "publication") if counts[stage]), key=lambda stage: counts[stage], default="survived")
    stage_rows = []
    for stage in ("retrieval", "cleanup", "deduplication", "extraction", "publication", "survived"):
        value = counts[stage]
        pct = round(100.0 * value / max(1, total), 2)
        stage_rows.append((stage, value, pct))

    lines = [
        "# Educational Content Forensics Report",
        "",
        "Scope: existing 15-pack Grade 8 concept-preservation pilot only.",
        "",
        "Read-only guarantee: this run queried Qdrant and inspected existing pack artifacts/reports; it did not regenerate packs or modify generation logic.",
        "",
        "## Final Answer",
        "",
        f"Educational concepts are first being lost primarily at: **{first_loss.title()}**.",
        "",
        "## Stage Loss Percentages",
        "",
        "| Stage | Concepts | Percent |",
        "| --- | ---: | ---: |",
    ]
    for stage, value, pct in stage_rows:
        lines.append(f"| {stage} | {value} | {pct:.2f}% |")
    lines.extend(
        [
            "",
            "## Evidence Summary",
            "",
            f"- Pilot chapters: {len(ground_truth)}",
            f"- Ground truth concept count: {sum(len(row.get('concepts', [])) for row in ground_truth)}",
            f"- Average Qdrant concept coverage: {average(qdrant_rows, 'coverage_percent')}%",
            f"- Cleanup removed chunks with concept loss: {sum(1 for row in cleanup_rows if row.get('concepts_lost'))}",
            f"- Deduplication removed chunks with concept loss: {sum(1 for row in dedupe_rows if row.get('concepts_lost'))}",
            f"- Average concept extractor precision: {average(extractor_rows, 'precision')}%",
            f"- Average concept extractor recall: {average(extractor_rows, 'recall')}%",
            f"- Average concept extractor F1: {average(extractor_rows, 'f1')}%",
            f"- Average retrieved formula coverage: {average(formula_rows, 'retrieved_formula_coverage_percent')}%",
            f"- Average published formula coverage: {average(formula_rows, 'published_formula_coverage_percent')}%",
            "",
            "## Required Files",
            "",
            "- ground_truth_concepts.json",
            "- qdrant_concept_coverage.json",
            "- cleanup_concept_loss_report.json",
            "- deduplication_concept_loss_report.json",
            "- concept_extractor_accuracy.json",
            "- formula_retention_report.json",
            "- concept_loss_root_cause.json",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ground_truth = build_ground_truth()
    qdrant_rows = audit_qdrant_retrieval(ground_truth)
    cleanup_rows = audit_cleanup_loss(ground_truth)
    dedupe_rows = audit_deduplication_loss(ground_truth)
    extractor_rows = audit_concept_extractor(ground_truth)
    formula_rows = audit_formula_retention(ground_truth)
    root_rows = audit_root_cause(ground_truth)

    write_json("ground_truth_concepts.json", ground_truth)
    write_json("qdrant_concept_coverage.json", qdrant_rows)
    write_json("cleanup_concept_loss_report.json", cleanup_rows)
    write_json("deduplication_concept_loss_report.json", dedupe_rows)
    write_json("concept_extractor_accuracy.json", extractor_rows)
    write_json("formula_retention_report.json", formula_rows)
    write_json("concept_loss_root_cause.json", root_rows)
    (OUT_DIR / "EDUCATIONAL_CONTENT_FORENSICS_REPORT.md").write_text(
        markdown(ground_truth, qdrant_rows, cleanup_rows, dedupe_rows, extractor_rows, formula_rows, root_rows),
        encoding="utf-8",
    )
    counts = Counter(row["lost_at"] for row in root_rows)
    print(json.dumps({"output_dir": str(OUT_DIR), "stage_counts": dict(counts)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
