from __future__ import annotations

from typing import Any

from .common import concept_present, percent, qdrant_query_chunks
from app.educational import EducationalConceptExtractor
from app.semantic_content_pipeline import SemanticContentPipeline


def audit_concept_extractor(ground_truth: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pipeline = SemanticContentPipeline()
    extractor = EducationalConceptExtractor()
    rows = []
    for item in ground_truth:
        retrieved = qdrant_query_chunks(8, item["subject"], item["chapter"])
        classified, _classification, _cleanup = pipeline._classify_and_clean(retrieved)
        deduped, _dedupe = pipeline._deduplicate(classified)
        extracted = extractor.extract(deduped, item)
        extracted_names = [concept.name for concept in extracted]
        gt = item.get("concepts", [])
        true_positive = sum(1 for concept in extracted_names if concept_present(concept, gt))
        precision = percent(true_positive, len(extracted_names))
        recall_count = sum(1 for concept in gt if concept_present(concept, extracted_names))
        recall = percent(recall_count, len(gt))
        f1 = round((2 * precision * recall / (precision + recall)) if precision + recall else 0.0, 2)
        rows.append(
            {
                "pack_id": item.get("pack_id"),
                "chapter": item.get("chapter"),
                "subject": item.get("subject"),
                "ground_truth_count": len(gt),
                "extracted_count": len(extracted_names),
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "missing_concepts": [concept for concept in gt if not concept_present(concept, extracted_names)][:40],
                "extracted_sample": extracted_names[:40],
            }
        )
    return rows

