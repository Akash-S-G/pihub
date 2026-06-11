from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from shared.text_normalization import normalize_curriculum_name


@dataclass(slots=True)
class StoredChunk:
    chunk_id: str
    text: str
    metadata: dict[str, Any]
    score: float | None = None


def make_qdrant_client(url: str) -> QdrantClient:
    return QdrantClient(url=url)


def ensure_collection(client: QdrantClient, collection_name: str, vector_size: int) -> None:
    collections = {collection.name for collection in client.get_collections().collections}
    if collection_name in collections:
        return

    client.create_collection(
        collection_name=collection_name,
        vectors_config=qmodels.VectorParams(size=vector_size, distance=qmodels.Distance.COSINE),
    )


def upsert_chunks(
    client: QdrantClient,
    collection_name: str,
    embeddings: list[list[float]],
    texts: list[str],
    metadatas: list[dict[str, Any]],
) -> list[str]:
    point_ids = [str(uuid.uuid4()) for _ in embeddings]
    points = [
        qmodels.PointStruct(
            id=point_id,
            vector=vector,
            payload={
                "text": text,
                **{
                    key: normalize_curriculum_name(value)
                    if key in {"subject", "chapter", "language", "topic", "section", "textbook_name"} and isinstance(value, str)
                    else value
                    for key, value in metadata.items()
                },
            },
        )
        for point_id, vector, text, metadata in zip(point_ids, embeddings, texts, metadatas, strict=True)
    ]
    client.upsert(collection_name=collection_name, points=points)
    return point_ids


def build_filter(metadata: dict[str, Any] | None = None) -> qmodels.Filter | None:
    if not metadata:
        return None

    conditions: list[qmodels.FieldCondition] = []
    for key, value in metadata.items():
        if value is None:
            continue
        if isinstance(value, str):
            value = normalize_curriculum_name(value)
        conditions.append(qmodels.FieldCondition(key=key, match=qmodels.MatchValue(value=value)))

    if not conditions:
        return None

    return qmodels.Filter(must=conditions)
