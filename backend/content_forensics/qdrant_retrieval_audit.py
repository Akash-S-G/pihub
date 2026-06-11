from __future__ import annotations

from typing import Any

from .common import concept_present, percent, qdrant_query_chunks


def audit_qdrant_retrieval(ground_truth: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for item in ground_truth:
        retrieved = qdrant_query_chunks(8, item["subject"], item["chapter"])
        texts = [str(chunk.get("text") or "") for chunk in retrieved]
        concepts = item.get("concepts", [])
        definitions = item.get("definitions", [])
        formulae = item.get("formulae", [])
        examples = [*item.get("examples", []), *item.get("worked_examples", [])]
        rows.append(
            {
                "pack_id": item.get("pack_id"),
                "chapter": item.get("chapter"),
                "subject": item.get("subject"),
                "retrieved_chunk_count": len(retrieved),
                "ground_truth_concepts": len(concepts),
                "retrieved_concepts": sum(1 for concept in concepts if concept_present(concept, texts)),
                "coverage_percent": percent(sum(1 for concept in concepts if concept_present(concept, texts)), len(concepts)),
                "definition_coverage_percent": percent(sum(1 for definition in definitions if concept_present(definition, texts)), len(definitions)),
                "formula_coverage_percent": percent(sum(1 for formula in formulae if concept_present(formula, texts)), len(formulae)),
                "example_coverage_percent": percent(sum(1 for example in examples if concept_present(example, texts)), len(examples)),
            }
        )
    return rows

