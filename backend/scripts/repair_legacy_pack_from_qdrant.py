#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from qdrant_client import QdrantClient, models

from app.pack_storage.pack_repository import PackRepository


def scroll_exact(
    client: QdrantClient,
    collection: str,
    grade: int,
    subject: str,
    chapter: str,
    language: str,
    limit: int,
) -> list[Any]:
    qfilter = models.Filter(
        must=[
            models.FieldCondition(key="grade", match=models.MatchValue(value=grade)),
            models.FieldCondition(key="subject", match=models.MatchValue(value=subject)),
            models.FieldCondition(key="chapter", match=models.MatchValue(value=chapter)),
            models.FieldCondition(key="language", match=models.MatchValue(value=language)),
        ]
    )
    points: list[Any] = []
    offset = None
    while len(points) < limit:
        batch, offset = client.scroll(
            collection_name=collection,
            scroll_filter=qfilter,
            limit=min(1000, limit - len(points)),
            offset=offset,
            with_payload=True,
            with_vectors=True,
        )
        if not batch:
            break
        points.extend(batch)
        if offset is None:
            break
    return points


def generate_glossary(content: list[dict[str, Any]]) -> list[dict[str, str]]:
    glossary: list[dict[str, str]] = []
    seen: set[str] = set()
    for chunk in content:
        metadata = chunk.get("metadata", {})
        term = str(metadata.get("topic") or metadata.get("chapter") or "").strip()
        definition = str(chunk.get("text") or "").strip()
        if not term or not definition:
            continue
        key = term.lower()
        if key in seen:
            continue
        seen.add(key)
        glossary.append({"term": term.capitalize(), "definition": definition[:240]})
        if len(glossary) >= 10:
            break
    return glossary


def build_artifacts(content: list[dict[str, Any]], pack_id: str) -> dict[str, Any]:
    return {
        "content": content,
        "glossary": generate_glossary(content),
        "quizzes": [
            {
                "question": f"What is the key idea in {chunk['metadata'].get('topic', chunk['metadata'].get('chapter', 'this section'))}?",
                "correct_answer": chunk["text"][:120],
            }
            for chunk in content[: max(1, min(5, len(content)))]
        ],
        "flashcards": [
            {"front": chunk["metadata"].get("topic", chunk["metadata"].get("chapter", "Term")), "back": chunk["text"][:160]}
            for chunk in content[: max(1, min(10, len(content)))]
        ],
        "summaries": [
            {"title": chunk["metadata"].get("chapter", pack_id), "text": chunk["text"][:200]}
            for chunk in content[: max(1, min(5, len(content)))]
        ],
        "enrichment": {
            "related_topics": sorted({chunk["metadata"].get("topic", "") for chunk in content if chunk["metadata"].get("topic")}),
            "prerequisites": sorted({chunk["metadata"].get("prerequisite", "") for chunk in content if chunk["metadata"].get("prerequisite")}),
        },
        "retrieval_index": {
            "vector_count": len(content),
            "version": "v2",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Repair one legacy pack ID by exact Qdrant metadata.")
    parser.add_argument("--pack-id", required=True)
    parser.add_argument("--grade", required=True, type=int)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--chapter", required=True)
    parser.add_argument("--language", default="english")
    parser.add_argument("--storage-path", default="/shared/packs")
    parser.add_argument("--qdrant-url", default="http://qdrant:6333")
    parser.add_argument("--collection", default="educational_chunks")
    parser.add_argument("--limit", type=int, default=10000)
    args = parser.parse_args()

    client = QdrantClient(url=args.qdrant_url)
    points = scroll_exact(client, args.collection, args.grade, args.subject, args.chapter, args.language, args.limit)
    if not points:
        raise SystemExit("No exact Qdrant chunks found; legacy repair blocked")

    content = [
        {
            "chunk_id": str(point.id),
            "text": (point.payload or {}).get("text", ""),
            "metadata": point.payload or {},
            "embedding": point.vector if point.vector else [],
        }
        for point in points
    ]
    repository = PackRepository(Path(args.storage_path))
    record = repository.save_pack(
        {
            "pack_id": args.pack_id,
            "grade": args.grade,
            "subject": args.subject,
            "chapter": args.chapter,
            "language": args.language,
            "version": "1.0.0",
            "artifacts": build_artifacts(content, args.pack_id),
            "generation_metadata": {
                "grade": args.grade,
                "subject": args.subject,
                "chapter": args.chapter,
                "language": args.language,
                "pack_type": "chapter",
                "legacy_exact_metadata_repair": True,
            },
        }
    )
    print(json.dumps({"pack_id": args.pack_id, "chunk_count": len(content), "archive_path": record.get("archive_path")}, indent=2))


if __name__ == "__main__":
    main()
