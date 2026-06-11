from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any

from .common import concept_present, normalize, qdrant_query_chunks
from app.semantic_content_pipeline import SemanticContentPipeline, stable_hash


def audit_deduplication_loss(ground_truth: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pipeline = SemanticContentPipeline()
    rows = []
    for item in ground_truth:
        retrieved = qdrant_query_chunks(8, item["subject"], item["chapter"])
        classified, _classification, _cleanup = pipeline._classify_and_clean(retrieved)
        exact_seen: set[str] = set()
        kept_norms: list[str] = []
        concepts = item.get("concepts", [])
        for chunk in classified:
            text = str(chunk.get("text") or "")
            digest = stable_hash(text)
            removed = False
            similarity = 1.0
            reason = ""
            if digest in exact_seen:
                removed = True
                reason = "exact_duplicate"
            else:
                best = max((SequenceMatcher(None, normalize(text), previous).ratio() for previous in kept_norms[-40:]), default=0.0)
                if best >= pipeline.near_duplicate_threshold:
                    removed = True
                    similarity = round(best, 4)
                    reason = "near_duplicate"
            if removed:
                rows.append(
                    {
                        "pack_id": item.get("pack_id"),
                        "chapter": item.get("chapter"),
                        "chunk_id": chunk.get("chunk_id"),
                        "removed_reason": reason,
                        "similarity_score": similarity,
                        "concepts_lost": [concept for concept in concepts if concept_present(concept, [text])],
                        "text_preview": text[:500],
                    }
                )
                continue
            exact_seen.add(digest)
            kept_norms.append(normalize(text))
    return rows

