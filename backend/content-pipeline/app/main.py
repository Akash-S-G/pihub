from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

import logging

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from qdrant_client import QdrantClient

from shared.config import get_settings
from shared.curriculum_graph import CurriculumGraph, create_sample_curriculum
from shared.schemas import (
    ChunkPreview,
    DebugRetrievalRequest,
    DirectoryIngestRequest,
    EducationalResource,
    HealthResponse,
    IngestResponse,
    Metadata,
    PackManifest,
    PackMetadata,
    SearchRequest,
    SearchResponse,
)
from shared.text_normalization import normalize_curriculum_name
from shared.vector_store import build_filter, ensure_collection, make_qdrant_client, upsert_chunks

logger = logging.getLogger(__name__)


def _sanitize_pack_id(s: str) -> str:
    """Create a filesystem-safe, slug-like pack id from arbitrary input."""
    if s is None:
        return ""
    slug = re.sub(r"[^A-Za-z0-9]+", "_", normalize_curriculum_name(str(s))).strip("_").lower()
    slug = re.sub(r"_+", "_", slug)
    return slug or "pack"

from app.auto_ingest import AutoIngestionService
from app.curriculum_graph.curriculum_router import CurriculumRouter
from app.curriculum_graph.graph_builder import GraphBuilder
from app.curriculum_graph.graph_storage import GraphStorage
from app.curriculum_graph.concept_index import ConceptIndex
from app.educational_intelligence import (
    EnrichmentRouter,
    FlashcardGenerator,
    GlossaryExtractor,
    PackCompiler,
    QualityEvaluator,
    QuizGenerator,
    SummaryGenerator,
)
from app.retrieval_engine.educational_retrieval_engine import EducationalRetrievalEngine
from app.textbook_ingest import StructuredTextbookIngest
from app.generated_pack_ingestor import GeneratedPackIngestor


settings = get_settings()
app = FastAPI(title="content-pipeline")


class SimpleEmbeddingModel:
    def __init__(self, dimension: int = 384) -> None:
        self.dimension = dimension

    def get_sentence_embedding_dimension(self) -> int:
        return self.dimension

    def encode(self, texts: list[str] | str, normalize_embeddings: bool = True) -> list[list[float]]:
        if isinstance(texts, str):
            texts = [texts]
        return [self._encode_one(text, normalize_embeddings) for text in texts]

    def _encode_one(self, text: str, normalize_embeddings: bool) -> list[float]:
        vector = [0.0] * self.dimension
        tokens = re.findall(r"[A-Za-z0-9']+", text.lower())
        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest, "big") % self.dimension
            vector[index] += 1.0

        if normalize_embeddings:
            norm = math.sqrt(sum(value * value for value in vector))
            if norm > 0:
                vector = [value / norm for value in vector]

        return vector


class Pipeline:
    def __init__(self) -> None:
        self.client = make_qdrant_client(settings.qdrant_url)
        self.embedding_model: SimpleEmbeddingModel | None = None
        self.collection_name = settings.qdrant_collection
        self.upload_dir = Path(settings.upload_dir)
        self.work_dir = Path(settings.work_dir)
        self.content_dir = Path(settings.content_dir)
        self.curriculum_graph_path = Path(settings.curriculum_graph_path)
        self.curriculum_relation_graph_path = Path(settings.curriculum_relation_graph_path)
        self.textbook_ingestor = StructuredTextbookIngest()
        self.curriculum_graph = CurriculumGraph.load(self.curriculum_graph_path)
        if not self.curriculum_graph.grades:
            self.curriculum_graph = create_sample_curriculum()
            self.curriculum_graph.save(self.curriculum_graph_path)
        self.concept_index = ConceptIndex()
        self.concept_manifest_paths = self._discover_concept_manifest_paths()
        self._rebuild_concept_index()
        self.ingestion_log: list[dict[str, Any]] = []
        self.auto_ingestion_service = AutoIngestionService(self.content_dir, self._auto_ingest_path) if settings.enable_auto_ingestion else None
        self.enable_curriculum_graph_engine = settings.enable_curriculum_graph_engine
        self.graph_storage = GraphStorage(self.curriculum_relation_graph_path)
        self.graph_builder = GraphBuilder()
        self.relation_graph = self.graph_storage.load() if self.enable_curriculum_graph_engine else {}
        self.enable_educational_retrieval_engine = settings.enable_educational_retrieval_engine
        self.retrieval_engine = EducationalRetrievalEngine()
        self.summary_generator = SummaryGenerator()
        self.glossary_extractor = GlossaryExtractor()
        self.quiz_generator = QuizGenerator()
        self.flashcard_generator = FlashcardGenerator()
        self.enrichment_router = EnrichmentRouter()
        self.pack_compiler = PackCompiler()
        self.quality_evaluator = QualityEvaluator()
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.content_dir.mkdir(parents=True, exist_ok=True)
        self.curriculum_graph_path.parent.mkdir(parents=True, exist_ok=True)
        self.curriculum_relation_graph_path.parent.mkdir(parents=True, exist_ok=True)

    def _load_model(self) -> SimpleEmbeddingModel:
        if self.embedding_model is None:
            self.embedding_model = SimpleEmbeddingModel()
        return self.embedding_model

    def _vector_size(self) -> int:
        return self._load_model().get_sentence_embedding_dimension()

    def _discover_concept_manifest_paths(self) -> list[Path]:
        current_file = Path(__file__).resolve()
        repo_root = current_file.parents[3] if len(current_file.parents) > 3 else current_file.parents[-1]
        candidate_paths = [
            Path(settings.curriculum_manifest_path),
            Path(settings.pack_registry_path),
            repo_root / "backend" / "curriculum-builder" / "curriculum_build" / "curriculum_manifest.json",
            repo_root / "backend" / "curriculum-builder" / "complete_build" / "curriculum_manifest.json",
            repo_root / "backend" / "curriculum-builder" / "complete_build" / "pack_registry.json",
        ]
        unique_paths: list[Path] = []
        seen: set[str] = set()
        for path in candidate_paths:
            resolved = str(path.resolve()) if path.exists() else str(path)
            if resolved in seen or not path.exists():
                continue
            seen.add(resolved)
            unique_paths.append(path)
        return unique_paths

    def _rebuild_concept_index(
        self,
        chunks: list[dict[str, Any]] | None = None,
        glossary_entries: list[dict[str, Any]] | None = None,
    ) -> None:
        self.concept_index.build_from_curriculum(
            self.curriculum_graph,
            manifest_paths=self.concept_manifest_paths,
            chunks=chunks,
            glossary_entries=glossary_entries,
        )

    def ensure_ready(self) -> None:
        ensure_collection(self.client, self.collection_name, self._vector_size())

    def _resolve_content_path(self, raw_path: str) -> Path:
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = self.content_dir / candidate
        resolved = candidate.resolve()
        content_root = self.content_dir.resolve()
        if resolved != content_root and content_root not in resolved.parents:
            raise HTTPException(status_code=400, detail="Path must be inside the configured content directory")
        return resolved

    def _merge_metadata(
        self,
        file_path: Path,
        metadata: Metadata | None = None,
        raw_text: str = "",
        source: str | None = None,
    ) -> dict[str, Any]:
        merged = self.textbook_ingestor.metadata_extractor.extract_from_path(file_path)
        if metadata is not None:
            merged.update(metadata.model_dump(exclude_none=True))
        merged = self.textbook_ingestor.metadata_extractor.merge_text_metadata(merged, raw_text)
        if merged.get("chapter"):
            merged["chapter"] = normalize_curriculum_name(str(merged["chapter"]))
        if merged.get("subject"):
            merged["subject"] = normalize_curriculum_name(str(merged["subject"]))
        if merged.get("language"):
            merged["language"] = normalize_curriculum_name(str(merged["language"]))
        if source:
            merged["source"] = source
        return merged

    def _ensure_topics(self, chunk: dict[str, Any]) -> list[str]:
        metadata = chunk.get("metadata", {})
        topics = list(metadata.get("topics") or [])
        if topics:
            return topics
        topics = self.curriculum_graph.infer_topics_for_query(chunk.get("text", ""))
        if topics:
            return topics
        return self.curriculum_graph.infer_concepts_for_text(chunk.get("text", ""), limit=4)

    @staticmethod
    def _tokenize_text(text: str) -> set[str]:
        return {
            token
            for token in re.findall(r"[\w\u0900-\u097F\u0C80-\u0CFF']+", text.lower())
            if token
        }

    def _lexical_relevance(self, query: str, hit: Any) -> float:
        payload = hit.payload or {}
        query_tokens = self._tokenize_text(query)
        payload_text = " ".join(
            [
                str(payload.get("text", "")),
                str(payload.get("subject", "")),
                str(payload.get("chapter", "")),
                str(payload.get("section", "")),
                " ".join(payload.get("topics", [])) if isinstance(payload.get("topics"), list) else str(payload.get("topics", "")),
                " ".join(payload.get("concepts", [])) if isinstance(payload.get("concepts"), list) else str(payload.get("concepts", "")),
            ]
        )
        payload_tokens = self._tokenize_text(payload_text)
        if not query_tokens or not payload_tokens:
            return float(hit.score or 0.0)

        overlap = len(query_tokens & payload_tokens) / max(len(query_tokens), 1)
        score = max(float(hit.score or 0.0), overlap)

        inferred_subject = self.curriculum_graph.infer_subject_for_query(query)
        if inferred_subject and str(payload.get("subject", "")).lower() == inferred_subject.lower():
            score = max(score, 0.65)

        inferred_topics = self.curriculum_graph.infer_topics_for_query(query)
        payload_topics = {str(topic).lower() for topic in (payload.get("topics") or [])}
        if any(topic.lower() in payload_topics for topic in inferred_topics):
            score = max(score, 0.8)

        chapter = str(payload.get("chapter", "")).lower()
        if chapter and any(token in chapter for token in query_tokens):
            score = max(score, 0.7)

        return score

    def _enrich_chunks(self, chunks: list[dict[str, Any]], base_metadata: dict[str, Any]) -> list[dict[str, Any]]:
        enriched: list[dict[str, Any]] = []
        for chunk in chunks:
            metadata = {**base_metadata, **chunk.get("metadata", {})}
            metadata.setdefault("source", base_metadata.get("source", "upload"))
            metadata.setdefault("language", base_metadata.get("language", "english"))
            inferred_subject = metadata.get("subject") or self.curriculum_graph.infer_subject_for_query(chunk.get("text", ""))
            if inferred_subject:
                metadata["subject"] = normalize_curriculum_name(str(inferred_subject))
            topics = self._ensure_topics(chunk)
            metadata["topics"] = [normalize_curriculum_name(str(topic)) for topic in topics if topic]
            concepts = self.curriculum_graph.infer_concepts_for_text(chunk.get("text", ""), limit=6)
            if concepts:
                metadata["concepts"] = concepts
            if not metadata.get("chapter") and base_metadata.get("chapter"):
                metadata["chapter"] = normalize_curriculum_name(str(base_metadata["chapter"]))
            if metadata.get("chapter"):
                metadata["chapter"] = normalize_curriculum_name(str(metadata["chapter"]))
            if metadata.get("section"):
                metadata["section"] = normalize_curriculum_name(str(metadata["section"]))
            if metadata.get("language"):
                metadata["language"] = normalize_curriculum_name(str(metadata["language"]))
            enriched.append({"text": chunk["text"], "metadata": metadata})
        return enriched

    def _prepare_response_metadata(self, metadata: dict[str, Any]) -> Metadata:
        return Metadata(
            grade=metadata.get("grade"),
            subject=metadata.get("subject"),
            chapter=metadata.get("chapter"),
            topic=(metadata.get("topics") or [metadata.get("topic") or None])[0] if (metadata.get("topics") or metadata.get("topic")) else None,
            language=metadata.get("language"),
        )

    def _store_chunks(self, chunks: list[dict[str, Any]]) -> None:
        if not chunks:
            return
        logger.info("Storing %d enriched chunks to vector store", len(chunks))
        print(f"[store] storing_chunks count={len(chunks)}")

        texts = [chunk["text"] for chunk in chunks]
        embedding_texts = []
        for chunk in chunks:
            metadata = chunk.get("metadata", {})
            prefix_parts = [
                str(metadata.get("grade") or ""),
                str(metadata.get("subject") or ""),
                str(metadata.get("chapter") or ""),
                str(metadata.get("section") or ""),
                " ".join(metadata.get("topics", [])),
                " ".join(metadata.get("concepts", [])),
            ]
            prefix = " ".join(part for part in prefix_parts if part).strip()
            embedding_texts.append(f"{prefix}\n\n{chunk['text']}" if prefix else chunk["text"])

        embeddings = self._load_model().encode(embedding_texts, normalize_embeddings=True)
        logger.info("Generated %d embeddings for %d chunks", len(embeddings), len(chunks))
        print(f"[store] embeddings_generated count={len(embeddings)}")
        metadatas = [chunk["metadata"] for chunk in chunks]
        point_ids = upsert_chunks(self.client, self.collection_name, embeddings, texts, metadatas)
        logger.info("Upserted %d vectors into collection %s", len(point_ids), self.collection_name)
        print(f"[store] upserted_vectors count={len(point_ids)} collection={self.collection_name}")
        self.curriculum_graph.build_from_chunks(chunks)
        self.curriculum_graph.save(self.curriculum_graph_path)
        glossary_entries = self.glossary_extractor.extract(chunks)
        # Rebuild lightweight concept index for routing
        try:
            self._rebuild_concept_index(chunks=chunks, glossary_entries=glossary_entries)
        except Exception:
            pass
        if self.enable_curriculum_graph_engine:
            self.relation_graph = self.graph_builder.build(chunks, existing=self.relation_graph)
            self.graph_storage.save(self.relation_graph)

    async def _auto_ingest_path(self, file_path: Path) -> None:
        await asyncio.to_thread(self._ingest_textbook_path, file_path, None, "watcher")

    def _ingest_textbook_path(self, file_path: Path, metadata: Metadata | None = None, source: str | None = None) -> dict[str, Any]:
        self.ensure_ready()
        raw_text = self.textbook_ingestor.extract_text_from_pdf(file_path)
        logger.info("Extracted text length for %s: %d", file_path.name, len(raw_text or ""))
        base_metadata = self._merge_metadata(file_path, metadata, raw_text, source=source or "textbook")
        chunks = self.textbook_ingestor.ingest_from_path(file_path, raw_text)
        logger.info("Detected %d raw chunks from chunker for %s", len(chunks), file_path.name)
        enriched_chunks = self._enrich_chunks(chunks, base_metadata)
        self._store_chunks(enriched_chunks)

        self.ingestion_log.append(
            {
                "file_name": file_path.name,
                "source_path": str(file_path),
                "chunks_created": len(enriched_chunks),
                "metadata": base_metadata,
            }
        )

        return {
            "file_name": file_path.name,
            "source_path": str(file_path),
            "chunks_created": len(enriched_chunks),
            "collection": self.collection_name,
            "metadata": self._prepare_response_metadata(base_metadata),
            "chunks": enriched_chunks,
        }

    def _split_into_sections(self, raw_text: str) -> list[dict[str, str]]:
        lines = [line.strip() for line in raw_text.splitlines()]
        sections: list[dict[str, str]] = []
        current_title = "Introduction"
        current_lines: list[str] = []

        def flush() -> None:
            text = "\n".join(line for line in current_lines if line).strip()
            if text:
                sections.append({"title": current_title, "text": text})

        for line in lines:
            if not line:
                continue
            is_heading = line.startswith("#") or (line.isupper() and len(line.split()) <= 8) or line.endswith(":")
            if is_heading and current_lines:
                flush()
                current_title = line.lstrip("# ").strip()
                current_lines = []
                continue
            if is_heading and not current_lines:
                current_title = line.lstrip("# ").strip()
                continue
            current_lines.append(line)

        flush()
        return sections or [{"title": "Document", "text": raw_text.strip()}]

    def _chunk_text(self, sections: list[dict[str, str]], metadata: Metadata) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for section in sections:
            text = section["text"].strip()
            if not text:
                continue

            start = 0
            while start < len(text):
                end = min(len(text), start + self.chunk_size)
                chunk_text = text[start:end].strip()
                if chunk_text:
                    results.append(
                        {
                            "text": chunk_text,
                            "metadata": {
                                **metadata.model_dump(exclude_none=True),
                                "section_title": section["title"],
                            },
                        }
                    )
                if end >= len(text):
                    break
                start = max(end - self.chunk_overlap, start + 1)
        return results

    def ingest_pdf(self, file_name: str, content: bytes, metadata: Metadata, source: str | None = None) -> IngestResponse:
        self.ensure_ready()
        target_path = self.upload_dir / file_name
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(content)

        result = self._ingest_textbook_path(target_path, metadata=metadata, source=source or "upload")
        return IngestResponse(
            file_name=file_name,
            chunks_created=result["chunks_created"],
            collection=self.collection_name,
            metadata=result["metadata"],
        )

    def ingest_textbook_directory(self, directory: Path, recursive: bool = True, source: str | None = None) -> dict[str, Any]:
        self.ensure_ready()
        directory = self._resolve_content_path(str(directory))
        pattern = "**/*.pdf" if recursive else "*.pdf"
        results: list[dict[str, Any]] = []
        total_chunks = 0

        for file_path in sorted(directory.glob(pattern)):
            try:
                result = self._ingest_textbook_path(file_path, metadata=None, source=source or "directory")
                results.append({
                    "file_name": result["file_name"],
                    "source_path": result["source_path"],
                    "chunks_created": result["chunks_created"],
                    "metadata": result["metadata"].model_dump(),
                })
                total_chunks += result["chunks_created"]
            except Exception as exc:
                results.append({"file_name": file_path.name, "source_path": str(file_path), "error": str(exc)})

        return {
            "directory": str(directory),
            "recursive": recursive,
            "files_processed": len(results),
            "chunks_created": total_chunks,
            "collection": self.collection_name,
            "results": results,
        }

    def _search(self, query: str, limit: int, filters: dict[str, Any] | None = None) -> SearchResponse:
        self.ensure_ready()
        query_vector = self._load_model().encode([query], normalize_embeddings=True)[0]
        requested_filters = dict(filters or {})
        routed_filters = dict(requested_filters)
        inferred_subject = self.curriculum_graph.infer_subject_for_query(query)
        inferred_topics = self.curriculum_graph.infer_topics_for_query(query)
        prerequisite_topics: list[str] = []
        related_topics: list[str] = []
        if self.enable_curriculum_graph_engine:
            route = CurriculumRouter(self.curriculum_graph, self.relation_graph).route(query, routed_filters)
            routed_filters = route.filters
            inferred_topics = route.expanded_topics or inferred_topics
            prerequisite_topics = route.prerequisite_topics
            related_topics = route.related_topics
        else:
            if inferred_subject and "subject" not in routed_filters:
                routed_filters["subject"] = inferred_subject
            if inferred_topics and "topic" not in routed_filters:
                routed_filters["topic"] = inferred_topics[0]

        # If topic was inferred (not explicit), avoid strict topic filter and rerank by educational priority.
        if self.enable_educational_retrieval_engine and "topic" in routed_filters and "topic" not in requested_filters:
            routed_filters.pop("topic", None)

        qfilter = build_filter(routed_filters)
        search_limit = max(limit * 4, 20) if self.enable_educational_retrieval_engine else max(limit * 2, 10)
        hits = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=search_limit,
            query_filter=qfilter,
            with_payload=True,
        )
        if self.enable_educational_retrieval_engine:
            results = self.retrieval_engine.rank(
                query=query,
                hits=hits,
                limit=limit,
                routed_filters=routed_filters,
                inferred_subject=inferred_subject,
                inferred_topics=inferred_topics,
                prerequisite_topics=prerequisite_topics,
                related_topics=related_topics,
            )
            # Keep response shape backward-compatible.
            for item in results:
                item.pop("ranking_debug", None)
                item.pop("vector_score", None)
        else:
            score_threshold = 0.3
            results = [
                {
                    "id": str(hit.id),
                    "score": self._lexical_relevance(query, hit),
                    "text": str((hit.payload or {}).get("text", "")),
                    "metadata": {k: v for k, v in (hit.payload or {}).items() if k != "text"},
                }
                for hit in hits
                if self._lexical_relevance(query, hit) >= score_threshold
            ]
        results = results[:limit]
        return SearchResponse(query=query, results=results)

    def debug_retrieval(self, query: str, limit: int, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        routed_filters = dict(metadata or {})
        inferred_subject = self.curriculum_graph.infer_subject_for_query(query)
        inferred_topics = self.curriculum_graph.infer_topics_for_query(query)
        expanded_topics: list[str] = []
        prerequisite_topics: list[str] = []
        related_topics: list[str] = []
        if self.enable_curriculum_graph_engine:
            route = CurriculumRouter(self.curriculum_graph, self.relation_graph).route(query, routed_filters)
            routed_filters = route.filters
            expanded_topics = route.expanded_topics
            prerequisite_topics = route.prerequisite_topics
            related_topics = route.related_topics
        elif inferred_subject and "subject" not in routed_filters:
            routed_filters["subject"] = inferred_subject
            if inferred_topics and "topic" not in routed_filters:
                routed_filters["topic"] = inferred_topics[0]

        query_vector = self._load_model().encode([query], normalize_embeddings=True)[0]
        hits = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=max(limit * 2, 10),
            query_filter=build_filter(routed_filters),
            with_payload=True,
        )
        if self.enable_educational_retrieval_engine:
            results = self.retrieval_engine.rank(
                query=query,
                hits=hits,
                limit=limit,
                routed_filters=routed_filters,
                inferred_subject=inferred_subject,
                inferred_topics=expanded_topics or inferred_topics,
                prerequisite_topics=prerequisite_topics,
                related_topics=related_topics,
            )
            for item in results:
                item["text"] = item["text"][:500]
        else:
            results = [
                {
                    "id": str(hit.id),
                    "score": self._lexical_relevance(query, hit),
                    "vector_score": float(hit.score) if hit.score is not None else None,
                    "text": str((hit.payload or {}).get("text", ""))[:500],
                    "metadata": {k: v for k, v in (hit.payload or {}).items() if k != "text"},
                }
                for hit in hits
            ]
        return {
            "query": query,
            "limit": limit,
            "inferred_subject": inferred_subject,
            "inferred_topics": inferred_topics,
            "expanded_topics": expanded_topics,
            "prerequisite_topics": prerequisite_topics,
            "related_topics": related_topics,
            "applied_filters": routed_filters,
            "results": results,
        }

    def debug_metadata(self, file_path: Path) -> dict[str, Any]:
        raw_text = self.textbook_ingestor.extract_text_from_pdf(file_path)
        base_metadata = self._merge_metadata(file_path, None, raw_text, source="debug")
        chunks = self.textbook_ingestor.ingest_from_path(file_path, raw_text)
        return {
            "file_name": file_path.name,
            "source_path": str(file_path),
            "metadata": base_metadata,
            "chunk_count": len(chunks),
            "preview_topics": self.curriculum_graph.infer_topics_for_query(raw_text),
            "preview_concepts": self.curriculum_graph.infer_concepts_for_text(raw_text),
        }

    def preview_chunks(self, file_path: Path) -> list[dict[str, Any]]:
        raw_text = self.textbook_ingestor.extract_text_from_pdf(file_path)
        base_metadata = self._merge_metadata(file_path, None, raw_text, source="preview")
        chunks = self.textbook_ingestor.ingest_from_path(file_path, raw_text)
        enriched = self._enrich_chunks(chunks, base_metadata)
        return [{"text": chunk["text"][:500], "metadata": chunk["metadata"]} for chunk in enriched]

    def similarity_score(self, left: str, right: str) -> float:
        left_vector = self._load_model().encode([left], normalize_embeddings=True)[0]
        right_vector = self._load_model().encode([right], normalize_embeddings=True)[0]
        return sum(a * b for a, b in zip(left_vector, right_vector, strict=True))

    def curriculum_search(self, query: str, limit: int = 1) -> dict[str, Any]:
        """Run previous (fallback) and curriculum-aware retrieval and return both.

        Returns a dict containing 'previous' and 'curriculum' results plus
        routing metadata (candidate_chapters, confidence).
        """
        previous = self._search(query, limit, None)

        candidates, confidence, inferred_subject = self.concept_index.route_query_to_chapters(query, self.curriculum_graph)

        if candidates and confidence >= 0.6:
            # restrict to the top candidate chapter
            chapter = candidates[0]
            filters: dict[str, Any] = {"chapter": chapter}
            if inferred_subject:
                filters["subject"] = inferred_subject
            curriculum_results = self._search(query, limit, filters)
        else:
            curriculum_results = previous

        return {
            "query": query,
            "candidate_chapters": candidates,
            "confidence": float(confidence),
            "inferred_subject": inferred_subject,
            "previous": previous.model_dump() if hasattr(previous, "model_dump") else previous,
            "curriculum": curriculum_results.model_dump() if hasattr(curriculum_results, "model_dump") else curriculum_results,
        }

    def build_pack_preview(self, chunks: list[dict[str, Any]], pack_name: str = "curriculum_pack") -> dict[str, Any]:
        if not chunks:
            manifest = PackManifest(pack_id=f"{pack_name}-empty", pack_name=pack_name, version="0.1.0")
            metadata = PackMetadata()
            return {"manifest": manifest.model_dump(), "metadata": metadata.model_dump(), "resources": []}

        first = chunks[0]["metadata"]
        topics: list[str] = []
        resource_types = ["experiment", "simulation", "animation", "diagram", "virtual_lab", "quiz", "html_interactive"]
        for chunk in chunks:
            for topic in chunk["metadata"].get("topics", []):
                if topic not in topics:
                    topics.append(topic)

        manifest = PackManifest(
            pack_id=f"{_sanitize_pack_id(pack_name)}-{_sanitize_pack_id(first.get('grade'))}-{_sanitize_pack_id(first.get('subject'))}",
            pack_name=pack_name,
            version="0.1.0",
            grade=first.get("grade"),
            subject=normalize_curriculum_name(str(first.get("subject"))) if first.get("subject") is not None else None,
            chapter=normalize_curriculum_name(str(first.get("chapter"))) if first.get("chapter") is not None else None,
            language=normalize_curriculum_name(str(first.get("language"))) if first.get("language") is not None else None,
            file_count=1,
            chunk_count=len(chunks),
        )
        metadata = PackMetadata(
            grade=first.get("grade"),
            subject=normalize_curriculum_name(str(first.get("subject"))) if first.get("subject") is not None else None,
            chapter=normalize_curriculum_name(str(first.get("chapter"))) if first.get("chapter") is not None else None,
            language=normalize_curriculum_name(str(first.get("language"))) if first.get("language") is not None else None,
            source=first.get("source"),
            curriculum_topics=topics,
            resource_types=resource_types,
        )
        resources = [
            EducationalResource(
                resource_type="diagram",
                topic=topic,
                grade_range=[first.get("grade")] if first.get("grade") is not None else [],
                offline_supported=True,
                interactive=False,
                source=first.get("source"),
            ).model_dump()
            for topic in topics[:5]
        ]
        return {"manifest": manifest.model_dump(), "metadata": metadata.model_dump(), "resources": resources}

    def build_learning_pack_preview(self, chunks: list[dict[str, Any]], pack_name: str = "curriculum_pack") -> dict[str, Any]:
        pack_preview = self.build_pack_preview(chunks, pack_name)
        if not chunks:
            empty_summary = self.summary_generator.generate([], chapter=None, topic=None)
            empty_glossary: list[dict[str, Any]] = []
            empty_quizzes: list[dict[str, Any]] = []
            empty_flashcards: list[dict[str, Any]] = []
            empty_enrichment: list[dict[str, Any]] = []
            empty_quality = self.quality_evaluator.evaluate([], empty_quizzes, empty_glossary)
            pack = self.pack_compiler.compile(pack_name, [], [empty_summary], empty_glossary, empty_quizzes, empty_flashcards, empty_enrichment)
            return {
                **pack_preview,
                "summary": empty_summary,
                "glossary": empty_glossary,
                "quizzes": empty_quizzes,
                "flashcards": empty_flashcards,
                "enrichment": empty_enrichment,
                "quality": empty_quality,
                "compiled_pack": pack,
            }

        first_metadata = chunks[0].get("metadata", {})
        chapter = first_metadata.get("chapter") or pack_name
        topic = (first_metadata.get("topics") or [first_metadata.get("topic") or None])[0]
        summary = self.summary_generator.generate(chunks, chapter=chapter, topic=topic)
        glossary = self.glossary_extractor.extract(chunks)
        quizzes = self.quiz_generator.generate(chunks)
        flashcards = self.flashcard_generator.generate(chunks)
        enrichment_context = self.enrichment_router.route(
            topic=topic or chapter,
            grade=first_metadata.get("grade"),
            subject=first_metadata.get("subject"),
        )
        quality = self.quality_evaluator.evaluate(chunks, quizzes, glossary)
        compiled = self.pack_compiler.compile(
            pack_name=pack_name,
            chunks=chunks,
            summaries=[summary],
            glossary=glossary,
            quizzes=quizzes,
            flashcards=flashcards,
            enrichment=enrichment_context["resources"],
        )

        return {
            **pack_preview,
            "summary": summary,
            "glossary": glossary,
            "quizzes": quizzes,
            "flashcards": flashcards,
            "enrichment": enrichment_context,
            "quality": quality,
            "compiled_pack": compiled,
        }


pipeline = Pipeline()


@app.on_event("startup")
async def startup() -> None:
    pipeline.ensure_ready()
    if pipeline.auto_ingestion_service is not None:
        await pipeline.auto_ingestion_service.startup()


@app.on_event("shutdown")
async def shutdown() -> None:
    if pipeline.auto_ingestion_service is not None:
        await pipeline.auto_ingestion_service.shutdown()


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    checks: dict[str, Any] = {"service": "ok"}
    try:
        pipeline.ensure_ready()
        checks["qdrant"] = {"status": "ok", "collection": pipeline.collection_name}
        checks["curriculum_graph"] = {
            "status": "ok",
            "grades": len(pipeline.curriculum_graph.grades),
            "path": str(pipeline.curriculum_graph_path),
        }
        return HealthResponse(status="ok", service="content-pipeline", checks=checks)
    except Exception as exc:
        checks["qdrant"] = {"status": "error", "detail": str(exc)}
        return HealthResponse(status="degraded", service="content-pipeline", checks=checks)


@app.post("/ingest/pdf", response_model=IngestResponse)
async def ingest_pdf(
    file: UploadFile = File(...),
    metadata: str = Form(default="{}"),
    source: str | None = Form(default=None),
) -> IngestResponse:
    try:
        metadata_model = Metadata.model_validate_json(metadata)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid metadata: {exc}") from exc

    content = await file.read()
    return await asyncio.to_thread(pipeline.ingest_pdf, file.filename or "upload.pdf", content, metadata_model, source)


@app.post("/ingest/textbook", response_model=IngestResponse)
async def ingest_textbook(
    file: UploadFile = File(...),
    metadata: str = Form(default="{}"),
    source: str | None = Form(default="textbook"),
) -> IngestResponse:
    try:
        metadata_model = Metadata.model_validate_json(metadata)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid metadata: {exc}") from exc
    content = await file.read()
    return await asyncio.to_thread(pipeline.ingest_pdf, file.filename or "upload.pdf", content, metadata_model, source)

try:
    from pydantic import BaseModel
except Exception:
    pass

class IngestGeneratedPackRequest(BaseModel):
    pack_id: str

@app.post("/ingest/generated-pack")
async def ingest_generated_pack(request: IngestGeneratedPackRequest) -> dict:
    try:
        ingestor = GeneratedPackIngestor(pipeline)
        return await asyncio.to_thread(ingestor.ingest_pack, request.pack_id)
    except Exception as e:
        logger.exception("Generated pack ingestion failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ingest/directory", response_model=IngestResponse)
async def ingest_directory(request: DirectoryIngestRequest) -> dict[str, Any]:
    directory = pipeline._resolve_content_path(request.directory)
    return await asyncio.to_thread(pipeline.ingest_textbook_directory, directory, request.recursive, request.source)


@app.post("/rag/search", response_model=SearchResponse)
async def rag_search(request: SearchRequest) -> SearchResponse:
    filters = request.metadata.model_dump(exclude_none=True) if request.metadata else None
    # Limit to 1 result for improved quality (Phase 3, Step 1)
    limit = 1
    return await asyncio.to_thread(pipeline._search, request.query, limit, filters)


@app.post("/rag/curriculum_search")
async def rag_curriculum_search(request: SearchRequest) -> dict[str, Any]:
    # Expose curriculum-aware retrieval that compares previous vs new results
    limit = max(1, min(request.limit, 10))
    return await asyncio.to_thread(pipeline.curriculum_search, request.query, limit)


@app.get("/rag/chapter", response_model=SearchResponse)
async def rag_chapter(chapter: str, limit: int = 5) -> SearchResponse:
    return await asyncio.to_thread(pipeline._search, chapter, limit, {"chapter": chapter})


@app.get("/rag/subject", response_model=SearchResponse)
async def rag_subject(subject: str, limit: int = 5) -> SearchResponse:
    return await asyncio.to_thread(pipeline._search, subject, limit, {"subject": subject})


@app.get("/debug/curriculum")
async def debug_curriculum() -> dict[str, Any]:
    return {"curriculum": pipeline.curriculum_graph.to_dict(), "path": str(pipeline.curriculum_graph_path)}


@app.get("/debug/curriculum-relations")
async def debug_curriculum_relations() -> dict[str, Any]:
    return {
        "enabled": pipeline.enable_curriculum_graph_engine,
        "path": str(pipeline.curriculum_relation_graph_path),
        "relations": pipeline.relation_graph,
    }


@app.get("/debug/metadata")
async def debug_metadata(path: str) -> dict[str, Any]:
    file_path = pipeline._resolve_content_path(path)
    return await asyncio.to_thread(pipeline.debug_metadata, file_path)


@app.get("/debug/chunks")
async def debug_chunks(path: str) -> dict[str, Any]:
    file_path = pipeline._resolve_content_path(path)
    chunks = await asyncio.to_thread(pipeline.preview_chunks, file_path)
    return {"path": str(file_path), "chunk_count": len(chunks), "chunks": chunks}


@app.post("/debug/retrieval")
async def debug_retrieval(request: DebugRetrievalRequest) -> dict[str, Any]:
    metadata = request.metadata.model_dump(exclude_none=True) if request.metadata else None
    return await asyncio.to_thread(pipeline.debug_retrieval, request.query, request.limit, metadata)


@app.get("/debug/similarity")
async def debug_similarity(left: str, right: str) -> dict[str, Any]:
    score = await asyncio.to_thread(pipeline.similarity_score, left, right)
    return {"left": left, "right": right, "score": score}


@app.get("/debug/pack-preview")
async def debug_pack_preview(path: str, pack_name: str = "curriculum_pack") -> dict[str, Any]:
    file_path = pipeline._resolve_content_path(path)
    chunks = await asyncio.to_thread(pipeline.preview_chunks, file_path)
    return await asyncio.to_thread(pipeline.build_pack_preview, chunks, pack_name)


@app.get("/debug/learning-pack-preview")
async def debug_learning_pack_preview(path: str, pack_name: str = "curriculum_pack") -> dict[str, Any]:
    file_path = pipeline._resolve_content_path(path)
    chunks = await asyncio.to_thread(pipeline.preview_chunks, file_path)
    return await asyncio.to_thread(pipeline.build_learning_pack_preview, chunks, pack_name)
