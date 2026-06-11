from __future__ import annotations

from typing import Any

from .common import concept_present, extract_formulas, percent, qdrant_query_chunks, archive_content_from_record, pack_records_for_pilot


def audit_formula_retention(ground_truth: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records = {pilot.pack_id: record for pilot, record in pack_records_for_pilot() if record}
    rows = []
    for item in ground_truth:
        retrieved = qdrant_query_chunks(8, item["subject"], item["chapter"])
        retrieved_texts = [str(chunk.get("text") or "") for chunk in retrieved]
        published_texts = []
        record = records.get(str(item.get("pack_id")))
        if record:
            published_texts = [str(chunk.get("text") or "") for chunk in archive_content_from_record(record)]
        source_formulas = item.get("formulae") or extract_formulas(" ".join(retrieved_texts))
        rows.append(
            {
                "pack_id": item.get("pack_id"),
                "chapter": item.get("chapter"),
                "source_formulas": len(source_formulas),
                "retrieved_formulas": sum(1 for formula in source_formulas if concept_present(formula, retrieved_texts)),
                "published_formulas": sum(1 for formula in source_formulas if concept_present(formula, published_texts)),
                "retrieved_formula_coverage_percent": percent(sum(1 for formula in source_formulas if concept_present(formula, retrieved_texts)), len(source_formulas)),
                "published_formula_coverage_percent": percent(sum(1 for formula in source_formulas if concept_present(formula, published_texts)), len(source_formulas)),
                "missing_published_formulas": [formula for formula in source_formulas if not concept_present(formula, published_texts)][:40],
            }
        )
    return rows

