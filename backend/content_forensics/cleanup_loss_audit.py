from __future__ import annotations

from typing import Any

from .common import concept_present, qdrant_query_chunks
from app.semantic_content_pipeline import SemanticContentPipeline


def audit_cleanup_loss(ground_truth: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pipeline = SemanticContentPipeline()
    rows = []
    for item in ground_truth:
        retrieved = qdrant_query_chunks(8, item["subject"], item["chapter"])
        concepts = item.get("concepts", [])
        for chunk in retrieved:
            text = pipeline._clean_text(str(chunk.get("text") or ""))
            row = {**chunk, "text": text}
            removal_reason = pipeline._removal_reason(
                {
                    **row,
                    "metadata": {
                        **(row.get("metadata") or {}),
                        "content_type": pipeline.__class__.__module__ and __import__("app.semantic_content_pipeline", fromlist=["classify_content"]).classify_content(text),
                    },
                }
            )
            if removal_reason:
                rows.append(
                    {
                        "pack_id": item.get("pack_id"),
                        "chapter": item.get("chapter"),
                        "chunk_id": chunk.get("chunk_id"),
                        "removed_reason": removal_reason,
                        "concepts_lost": [concept for concept in concepts if concept_present(concept, [str(chunk.get("text") or "")])],
                        "text_preview": str(chunk.get("text") or "")[:500],
                    }
                )
    return rows

