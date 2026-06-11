from __future__ import annotations

from typing import Any

from .common import archive_content_from_record, concept_present, pack_records_for_pilot, qdrant_query_chunks
from app.educational import EducationalConceptExtractor
from app.semantic_content_pipeline import SemanticContentPipeline


def audit_root_cause(ground_truth: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records = {pilot.pack_id: record for pilot, record in pack_records_for_pilot() if record}
    pipeline = SemanticContentPipeline()
    extractor = EducationalConceptExtractor()
    rows = []
    for item in ground_truth:
        retrieved = qdrant_query_chunks(8, item["subject"], item["chapter"])
        retrieved_texts = [str(chunk.get("text") or "") for chunk in retrieved]
        classified, _classification, _cleanup = pipeline._classify_and_clean(retrieved)
        cleanup_texts = [str(chunk.get("text") or "") for chunk in classified]
        deduped, _dedupe = pipeline._deduplicate(classified)
        dedupe_texts = [str(chunk.get("text") or "") for chunk in deduped]
        extracted = extractor.extract(deduped, item)
        extracted_names = [concept.name for concept in extracted]
        record = records.get(str(item.get("pack_id")))
        published_texts = [str(chunk.get("text") or "") for chunk in archive_content_from_record(record)] if record else []
        for concept in item.get("concepts", []):
            if not concept_present(concept, retrieved_texts):
                lost_at = "retrieval"
            elif not concept_present(concept, cleanup_texts):
                lost_at = "cleanup"
            elif not concept_present(concept, dedupe_texts):
                lost_at = "deduplication"
            elif not concept_present(concept, extracted_names):
                lost_at = "extraction"
            elif not concept_present(concept, published_texts):
                lost_at = "publication"
            else:
                lost_at = "survived"
            rows.append({"pack_id": item.get("pack_id"), "chapter": item.get("chapter"), "concept": concept, "lost_at": lost_at})
    return rows

