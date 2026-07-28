from __future__ import annotations

"""Persist enrichment records (videos, articles, simulations, real-world
examples) into a dedicated Qdrant collection so the offline app can retrieve
them semantically alongside chunks.

Each record is embedded from a compact "topic + title + description" text and
stored with rich payload metadata (including the local media path when the asset
was downloaded by MediaStore). Falls back silently if Qdrant is unavailable.
"""

import logging
from typing import Any

from shared.config import get_settings
from shared.vector_store import ensure_collection, make_qdrant_client, upsert_chunks

logger = logging.getLogger(__name__)


class EnrichmentStore:
    """Store enrichment resources in Qdrant (separate collection from chunks)."""

    def __init__(self, embedding_model: Any, collection_name: str | None = None) -> None:
        s = get_settings()
        self.collection_name = collection_name or s.enrichment_collection
        self.qdrant_url = s.qdrant_url
        self.embedding_model = embedding_model
        self._client: Any | None = None
        self._ready = False

    def _get_client(self) -> Any | None:
        if self._client is None:
            try:
                self._client = make_qdrant_client(self.qdrant_url)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Qdrant unavailable for enrichment store: %s", str(exc)[:150])
                return None
        return self._client

    def _ensure(self) -> bool:
        if self._ready:
            return True
        client = self._get_client()
        if client is None:
            return False
        try:
            dim = int(self.embedding_model.get_sentence_embedding_dimension())
            ensure_collection(client, self.collection_name, dim, self.qdrant_url)
            self._ready = True
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not ensure enrichment collection: %s", str(exc)[:150])
            return False
        return True

    def store(self, records: list[dict[str, Any]]) -> int:
        """Upsert enrichment records. Returns the number persisted.

        Each record must carry at least ``resource_type`` and ``title``; optional
        keys (``url``, ``local_path``, ``topic``, ``language``, ``subject``,
        ``chapter``, ``grade``, ``source``, ``description``) become payload.
        """
        if not records or not self._ensure():
            return 0
        client = self._get_client()
        if client is None:
            return 0

        texts: list[str] = []
        embed_texts: list[str] = []
        metadatas: list[dict[str, Any]] = []
        for rec in records:
            topic = str(rec.get("topic", ""))
            title = str(rec.get("title", ""))
            desc = str(rec.get("description", ""))
            text = " — ".join(p for p in (title, desc) if p) or topic
            embed_texts.append(" ".join(p for p in (topic, title, desc) if p) or text)
            texts.append(text)
            metadatas.append({k: v for k, v in rec.items() if v is not None and k != "description"} | {"description": desc})

        try:
            embeddings = self.embedding_model.encode(embed_texts, normalize_embeddings=True)
            ids = upsert_chunks(client, self.collection_name, embeddings, texts, metadatas)
            logger.info("Stored %d enrichment records in %s", len(ids), self.collection_name)
            return len(ids)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Enrichment upsert failed: %s", str(exc)[:200])
            return 0

    @staticmethod
    def flatten_topic_enrichment(
        topic_enrichment: list[dict[str, Any]],
        real_world: list[dict[str, Any]] | None = None,
        base_meta: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Turn the agent's per-topic enrichment (+ real-world examples) into a
        flat list of records ready for :meth:`store`."""
        base_meta = base_meta or {}
        records: list[dict[str, Any]] = []
        for topic_block in topic_enrichment:
            topic = topic_block.get("topic", "")
            language = topic_block.get("language", base_meta.get("language", "en"))
            for kind in ("videos", "articles", "references", "simulations"):
                for item in topic_block.get(kind, []):
                    records.append({
                        "resource_type": item.get("resource_type") or kind.rstrip("s"),
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "local_path": item.get("local_path", ""),
                        "source": item.get("source", ""),
                        "description": item.get("description", ""),
                        "thumbnail": item.get("thumbnail", ""),
                        "topic": topic,
                        "language": item.get("language", language),
                        "subject": base_meta.get("subject"),
                        "chapter": base_meta.get("chapter"),
                        "grade": base_meta.get("grade"),
                    })
        for ex in (real_world or []):
            records.append({
                "resource_type": "real_world_example",
                "title": ex.get("concept", ""),
                "description": " ".join(p for p in (ex.get("real_world_use", ""), ex.get("explanation", "")) if p),
                "topic": ex.get("concept", ""),
                "language": base_meta.get("language", "en"),
                "subject": base_meta.get("subject"),
                "chapter": base_meta.get("chapter"),
                "grade": base_meta.get("grade"),
            })
        return records
