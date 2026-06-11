"""
Pack Management Core Service

Handles:
- Pack generation from Qdrant vectors + curriculum
- Pack compression and versioning
- Pack manifest generation
- Pack storage and retrieval
- Pack integrity validation
"""

import asyncio
import hashlib
import json
import logging
import re
import shutil
import tarfile
import zlib
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import gzip
import io

import httpx
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

from app.pack_storage.pack_repository import PackRepository
from app.semantic_content_pipeline import SemanticContentPipeline
from shared.text_normalization import normalize_curriculum_name

logger = logging.getLogger(__name__)

SUBJECT_QUERY_ALIASES = {
    "math": ["maths", "mathematics"],
    "maths": ["maths", "math", "mathematics"],
    "mathematics": ["maths", "math", "mathematics"],
    "science": ["science", "social_science"],
    "social_science": ["social_science", "science"],
    "social science": ["social_science", "science"],
    "history": ["social_science", "history"],
    "geography": ["social_science", "geography"],
    "economics": ["social_science", "economics"],
    "civics": ["social_science", "civics"],
}


class PackGenerationNoContentError(RuntimeError):
    """Raised when no chunks are available for a requested pack."""


class PackQualityGateError(RuntimeError):
    """Raised when generated content does not satisfy publication quality gates."""


class PackGenerator:
    """Core pack generation engine"""
    
    def __init__(
        self,
        qdrant_url: str,
        qdrant_collection: str,
        pack_storage_path: str,
        curriculum_graph_path: str
    ):
        self.qdrant_url = qdrant_url
        self.qdrant_collection = qdrant_collection
        self.pack_storage_path = Path(pack_storage_path)
        self.curriculum_graph_path = Path(curriculum_graph_path)
        
        self.pack_storage_path.mkdir(parents=True, exist_ok=True)
        self.client = QdrantClient(url=qdrant_url)
        self.repository = PackRepository(self.pack_storage_path)
        self.semantic_pipeline = SemanticContentPipeline()
        
        self.active_generations: Dict[str, dict] = {}
    
    async def generate_class_pack(
        self,
        grade: int,
        subject: str,
        language: str = "english",
        include_media: bool = False,
        compression: str = "gzip",
        quantize_embeddings: bool = False
    ) -> str:
        """
        Generate a comprehensive pack for an entire class
        
        Args:
            grade: Grade level (e.g., 7)
            subject: Subject name (e.g., 'science')
            language: Language code (e.g., 'en', 'kn')
            include_media: Include media files
            compression: Compression format
            quantize_embeddings: Quantize embeddings to reduce size
        
        Returns:
            Pack ID
        """
        normalized_subject = normalize_curriculum_name(subject)
        normalized_language = normalize_curriculum_name(language)
        pack_id = f"class{grade}_{self._pack_id_part(normalized_subject)}_{self._pack_id_part(normalized_language)}"
        logger.info(f"Starting class pack generation: {pack_id}")
        
        # Search Qdrant for all chunks matching grade/subject/language
        search_results = await self._search_chunks_by_metadata(
            grade=grade,
            subject=subject,
            language=language
        )
        self._ensure_chunks_found(pack_id, search_results)
        
        pack = await self._create_pack(
            pack_id=pack_id,
            pack_type="class",
            chunks=search_results,
            metadata={
                "grade": grade,
                "subject": normalized_subject,
                "language": normalized_language
            },
            compression=compression,
            quantize_embeddings=quantize_embeddings,
            include_media=include_media
        )
        
        logger.info(f"Class pack generated: {pack_id}, size: {pack['size_mb']:.2f}MB")
        return pack_id
    
    async def generate_chapter_pack(
        self,
        grade: int,
        subject: str,
        chapter: str,
        language: str = "english",
        compression: str = "gzip",
        quantize_embeddings: bool = False
    ) -> str:
        """Generate a pack for a specific chapter"""
        normalized_subject = normalize_curriculum_name(subject)
        normalized_chapter = normalize_curriculum_name(chapter)
        normalized_language = normalize_curriculum_name(language)
        pack_id = f"chapter_{grade}_{self._pack_id_part(normalized_subject)}_{self._pack_id_part(normalized_chapter)}_{self._pack_id_part(normalized_language)}"
        logger.info(f"Starting chapter pack generation: {pack_id}")
        
        # Search for chunks with matching chapter
        search_results = await self._search_chunks_by_metadata(
            grade=grade,
            subject=subject,
            chapter=chapter,
            language=language
        )
        self._ensure_chunks_found(pack_id, search_results)
        
        pack = await self._create_pack(
            pack_id=pack_id,
            pack_type="chapter",
            chunks=search_results,
            metadata={
                "grade": grade,
                "subject": normalized_subject,
                "chapter": normalized_chapter,
                "language": normalized_language
            },
            compression=compression,
            quantize_embeddings=quantize_embeddings
        )
        
        logger.info(f"Chapter pack generated: {pack_id}, size: {pack['size_mb']:.2f}MB")
        return pack_id
    
    async def generate_language_pack(
        self,
        language: str,
        grade: Optional[int] = None,
        subject: Optional[str] = None,
        compression: str = "gzip",
        quantize_embeddings: bool = False
    ) -> str:
        """Generate a language-specific pack"""
        normalized_language = normalize_curriculum_name(language)
        normalized_subject = normalize_curriculum_name(subject) if subject else None
        subject_str = f"_{self._pack_id_part(normalized_subject)}" if normalized_subject else ""
        grade_str = f"_{grade}" if grade else ""
        pack_id = f"lang_{self._pack_id_part(normalized_language)}{grade_str}{subject_str}"
        logger.info(f"Starting language pack generation: {pack_id}")
        
        # Search for chunks with matching language
        search_results = await self._search_chunks_by_metadata(
            language=language,
            grade=grade,
            subject=subject
        )
        self._ensure_chunks_found(pack_id, search_results)
        
        pack = await self._create_pack(
            pack_id=pack_id,
            pack_type="language",
            chunks=search_results,
            metadata={
                "language": normalized_language,
                "grade": grade,
                "subject": normalized_subject
            },
            compression=compression,
            quantize_embeddings=quantize_embeddings
        )
        
        logger.info(f"Language pack generated: {pack_id}, size: {pack['size_mb']:.2f}MB")
        return pack_id
    
    async def _search_chunks_by_metadata(
        self,
        grade: Optional[int] = None,
        subject: Optional[str] = None,
        chapter: Optional[str] = None,
        language: Optional[str] = None,
        limit: int = 10000
    ) -> List[dict]:
        """Search Qdrant for chunks matching metadata filters with controlled fallbacks."""
        try:
            requested = {
                "grade": grade,
                "subject": self._normalize_metadata_value(subject),
                "chapter": self._normalize_metadata_value(chapter),
                "language": self._normalize_metadata_value(language),
            }

            logger.info(
                "Pack generation request metadata: grade=%s, subject=%s, chapter=%s, language=%s",
                requested["grade"],
                requested["subject"],
                requested["chapter"],
                requested["language"],
            )

            exact = self._scroll_chunks_by_metadata(
                grade=requested["grade"],
                subject=requested["subject"],
                chapter=requested["chapter"],
                language=requested["language"],
                limit=limit,
            )
            if exact:
                logger.info("Found %s chunks matching exact filters", len(exact))
                return exact

            logger.warning(
                "PACK_FALLBACK_TRIGGERED grade=%s subject=%s chapter=%s language=%s reason=exact_filter_zero_chunks",
                requested["grade"],
                requested["subject"],
                requested["chapter"],
                requested["language"],
            )

            attempts = self._fallback_attempts(
                grade=requested["grade"],
                subject=requested["subject"],
                chapter=requested["chapter"],
                language=requested["language"],
            )
            for attempt in attempts:
                if attempt["fuzzy_chapter"]:
                    results = self._scroll_chunks_with_fuzzy_chapter(
                        grade=attempt["grade"],
                        subject=attempt["subject"],
                        chapter=attempt["chapter"],
                        language=attempt["language"],
                        limit=max(limit, 50000),
                    )
                else:
                    results = self._scroll_chunks_by_metadata(
                        grade=attempt["grade"],
                        subject=attempt["subject"],
                        chapter=attempt["chapter"],
                        language=attempt["language"],
                        limit=limit,
                    )

                if results:
                    logger.warning(
                        "PACK_FALLBACK_SUCCESS reason=%s chunks=%s grade=%s subject=%s chapter=%s language=%s fuzzy_chapter=%s",
                        attempt["reason"],
                        len(results),
                        attempt["grade"],
                        attempt["subject"],
                        attempt["chapter"],
                        attempt["language"],
                        attempt["fuzzy_chapter"],
                    )
                    return results

            logger.warning(
                "PACK_FALLBACK_FAILED grade=%s subject=%s chapter=%s language=%s",
                requested["grade"],
                requested["subject"],
                requested["chapter"],
                requested["language"],
            )
            return []
        
        except Exception as e:
            logger.exception("Error searching chunks: %s", e)
            return []

    @staticmethod
    def _normalize_metadata_value(value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            return normalize_curriculum_name(value)
        return value

    @staticmethod
    def _unique(values: List[Any]) -> List[Any]:
        result: List[Any] = []
        seen = set()
        for value in values:
            if value in (None, ""):
                continue
            key = str(value)
            if key in seen:
                continue
            seen.add(key)
            result.append(value)
        return result

    def _subject_query_variants(self, subject: Optional[str]) -> List[str]:
        if not subject:
            return []
        normalized = normalize_curriculum_name(subject)
        variants = [normalized]
        variants.extend(SUBJECT_QUERY_ALIASES.get(normalized, []))
        return [str(value) for value in self._unique(variants)]

    def _fallback_attempts(
        self,
        grade: Optional[int],
        subject: Optional[str],
        chapter: Optional[str],
        language: Optional[str],
    ) -> List[dict[str, Any]]:
        attempts: List[dict[str, Any]] = []
        subject_variants = self._subject_query_variants(subject) or [subject]

        def add(reason: str, item_subject: Optional[str], item_language: Optional[str], fuzzy_chapter: bool = False) -> None:
            attempt = {
                "reason": reason,
                "grade": grade,
                "subject": item_subject,
                "chapter": chapter,
                "language": item_language,
                "fuzzy_chapter": fuzzy_chapter,
            }
            key = (
                attempt["reason"],
                attempt["grade"],
                attempt["subject"],
                attempt["chapter"],
                attempt["language"],
                attempt["fuzzy_chapter"],
            )
            if not any(
                (
                    existing["reason"],
                    existing["grade"],
                    existing["subject"],
                    existing["chapter"],
                    existing["language"],
                    existing["fuzzy_chapter"],
                ) == key
                for existing in attempts
            ):
                attempts.append(attempt)

        if language is not None:
            add("remove_language_filter", subject, None)

        for variant in subject_variants:
            if variant != subject:
                add("normalized_subject_filter", variant, language)
                if language is not None:
                    add("normalized_subject_without_language", variant, None)

        if chapter is not None:
            add("chapter_fuzzy_match", subject, language, fuzzy_chapter=True)
            if language is not None:
                add("chapter_fuzzy_match_without_language", subject, None, fuzzy_chapter=True)
            for variant in subject_variants:
                if variant != subject:
                    add("normalized_subject_chapter_fuzzy_match", variant, language, fuzzy_chapter=True)
                    if language is not None:
                        add("normalized_subject_chapter_fuzzy_without_language", variant, None, fuzzy_chapter=True)

        return attempts

    def _build_qdrant_filter(
        self,
        grade: Optional[int] = None,
        subject: Optional[str] = None,
        chapter: Optional[str] = None,
        language: Optional[str] = None,
    ):
        from qdrant_client import models

        must_conditions = []
        conditions = []
        for key, value in (
            ("grade", grade),
            ("subject", subject),
            ("chapter", chapter),
            ("language", language),
        ):
            if value is None:
                continue
            conditions.append({"key": key, "match": {"value": value}})
            must_conditions.append(models.FieldCondition(key=key, match=models.MatchValue(value=value)))

        scroll_filter = models.Filter(must=must_conditions) if must_conditions else None
        logger.info("Generated Qdrant filter: %s", conditions)
        logger.info("EXACT GENERATED FILTER OBJECT: %s", scroll_filter)
        if scroll_filter:
            try:
                logger.info("SERIALIZED JSON FILTER: %s", scroll_filter.json())
            except AttributeError:
                logger.info("SERIALIZED JSON FILTER: %s", scroll_filter.model_dump_json())
        return scroll_filter

    def _scroll_points(self, scroll_filter: Any, limit: int) -> list[Any]:
        points: list[Any] = []
        offset = None
        while len(points) < limit:
            batch, offset = self.client.scroll(
                collection_name=self.qdrant_collection,
                scroll_filter=scroll_filter,
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
        logger.info("Number of Qdrant points returned after pagination: %s", len(points))
        if points and points[0].payload:
            logger.info("First returned payload: %s", points[0].payload)
        return points

    @staticmethod
    def _point_to_result(point: Any) -> dict[str, Any]:
        payload = point.payload or {}
        return {
            "chunk_id": str(point.id),
            "text": payload.get("text", ""),
            "embedding": point.vector if point.vector else [],
            "metadata": payload,
        }

    def _scroll_chunks_by_metadata(
        self,
        grade: Optional[int] = None,
        subject: Optional[str] = None,
        chapter: Optional[str] = None,
        language: Optional[str] = None,
        limit: int = 10000,
    ) -> List[dict]:
        scroll_filter = self._build_qdrant_filter(
            grade=grade,
            subject=subject,
            chapter=chapter,
            language=language,
        )
        return [self._point_to_result(point) for point in self._scroll_points(scroll_filter, limit)]

    @staticmethod
    def _chapter_matches(candidate: Any, expected: Optional[str]) -> bool:
        if expected is None:
            return True
        candidate_norm = normalize_curriculum_name(str(candidate or ""))
        expected_norm = normalize_curriculum_name(str(expected or ""))
        if not candidate_norm or not expected_norm:
            return False
        if candidate_norm == expected_norm:
            return True
        if candidate_norm in expected_norm or expected_norm in candidate_norm:
            return True
        return SequenceMatcher(None, candidate_norm, expected_norm).ratio() >= 0.82

    def _scroll_chunks_with_fuzzy_chapter(
        self,
        grade: Optional[int],
        subject: Optional[str],
        chapter: Optional[str],
        language: Optional[str],
        limit: int,
    ) -> List[dict]:
        scroll_filter = self._build_qdrant_filter(
            grade=grade,
            subject=subject,
            language=language,
        )
        results: List[dict] = []
        for point in self._scroll_points(scroll_filter, limit):
            payload = point.payload or {}
            if self._chapter_matches(payload.get("chapter"), chapter):
                results.append(self._point_to_result(point))
        logger.info(
            "Fuzzy chapter match found %s chunks for chapter=%s subject=%s language=%s",
            len(results),
            chapter,
            subject,
            language,
        )
        return results

    @staticmethod
    def _ensure_chunks_found(pack_id: str, chunks: List[dict]) -> None:
        if chunks:
            return
        logger.error("Pack generation failed: zero chunks retrieved for pack_id=%s", pack_id)
        raise PackGenerationNoContentError(f"No chunks found for pack {pack_id}; empty pack publication blocked")

    def debug_pack_query(
        self,
        grade: int = 5,
        subject: str = "maths",
        chapter: str = "animal jumps"
    ):
        """Debug method to identify the exact mismatch between fields."""
        try:
            from qdrant_client import models
            print("\n--- RUNNING DEBUG PACK QUERY ---")
            
            language = "english"
            normalized_subject = normalize_curriculum_name(subject)
            normalized_chapter = normalize_curriculum_name(chapter)
            normalized_language = normalize_curriculum_name(language)
            
            # Filter A: All fields
            must_conditions_A = [
                models.FieldCondition(key="grade", match=models.MatchValue(value=grade)),
                models.FieldCondition(key="subject", match=models.MatchValue(value=normalized_subject)),
                models.FieldCondition(key="chapter", match=models.MatchValue(value=normalized_chapter)),
                models.FieldCondition(key="language", match=models.MatchValue(value=normalized_language))
            ]
            filter_A = models.Filter(must=must_conditions_A)
            
            points_A, _ = self.client.scroll(
                collection_name=self.qdrant_collection,
                scroll_filter=filter_A,
                limit=10,
                with_payload=True
            )
            print(f"Filter A (All fields) chunk count: {len(points_A)}")
            
            # Filter B: Only chapter
            must_conditions_B = [
                models.FieldCondition(key="chapter", match=models.MatchValue(value=normalized_chapter))
            ]
            filter_B = models.Filter(must=must_conditions_B)
            
            points_B, _ = self.client.scroll(
                collection_name=self.qdrant_collection,
                scroll_filter=filter_B,
                limit=10,
                with_payload=True
            )
            print(f"Filter B (Only chapter) chunk count: {len(points_B)}")
            
            if len(points_B) > 0 and len(points_A) == 0:
                print("\nFinding mismatch...")
                payload = points_B[0].payload
                print(f"First matching payload for B:\n{json.dumps(payload, indent=2)}")
                
                test_fields = [
                    ("grade", grade),
                    ("subject", normalized_subject),
                    ("language", normalized_language)
                ]
                
                for field, expected_val in test_fields:
                    test_conds = [
                        models.FieldCondition(key="chapter", match=models.MatchValue(value=normalized_chapter)),
                        models.FieldCondition(key=field, match=models.MatchValue(value=expected_val))
                    ]
                    test_filter = models.Filter(must=test_conds)
                    test_pts, _ = self.client.scroll(
                        collection_name=self.qdrant_collection,
                        scroll_filter=test_filter,
                        limit=1,
                        with_payload=False
                    )
                    if len(test_pts) == 0:
                        actual_val = payload.get(field)
                        print(f"MISMATCH FOUND! Field: '{field}'")
                        print(f"  Expected value used in query: '{expected_val}' (type: {type(expected_val).__name__})")
                        print(f"  Actual value in Qdrant DB : '{actual_val}' (type: {type(actual_val).__name__})")

            print("--- END DEBUG PACK QUERY ---\n")
        except Exception as e:
            print(f"Error in debug: {e}")

    @staticmethod
    def _pack_id_part(value: str | None) -> str:
        normalized = normalize_curriculum_name(value)
        return re.sub(r"[^a-z0-9]+", "_", normalized).strip("_") or "unknown"
        
    def _generate_glossary(self, chunks: List[dict]) -> List[dict]:
        """Generate a valid, deduplicated glossary from chunks"""
        glossary = []
        seen_terms = set()
        
        for chunk in chunks:
            metadata = chunk.get("metadata", {})
            term = metadata.get("topic") or metadata.get("chapter") or ""
            term = str(term).strip()
            
            if not term:
                continue
                
            # Normalize casing: e.g. capitalize first letter
            term_normalized = term.capitalize()
            term_lower = term_normalized.lower()
            
            if term_lower in seen_terms:
                continue
                
            definition = str(chunk.get("text", "")).strip()
            if not definition:
                continue
                
            # Truncate definition reasonably
            definition = definition[:240]
            
            glossary.append({"term": term_normalized, "definition": definition})
            seen_terms.add(term_lower)
            
            if len(glossary) >= 10:
                break
                
        return glossary
    
    async def _create_pack(
        self,
        pack_id: str,
        pack_type: str,
        chunks: List[dict],
        metadata: dict,
        compression: str = "gzip",
        quantize_embeddings: bool = False,
        include_media: bool = False
    ) -> dict:
        """Create and compress a pack"""
        processed_chunks: list[dict[str, object]] = []
        for chunk in chunks:
            chunk_data = {
                "chunk_id": chunk["chunk_id"],
                "text": chunk["text"],
                "metadata": chunk["metadata"],
            }
            if quantize_embeddings and chunk.get("embedding"):
                chunk_data["embedding"] = self._quantize_embedding(chunk["embedding"])
            else:
                chunk_data["embedding"] = chunk.get("embedding", [])
            processed_chunks.append(chunk_data)

        semantic_result = self.semantic_pipeline.build(processed_chunks, pack_id=pack_id, metadata=metadata)
        if not semantic_result.quality_gate.get("passed"):
            logger.error(
                "PACK_QUALITY_GATE_FAILED pack_id=%s failures=%s metrics=%s",
                pack_id,
                semantic_result.quality_gate.get("failures"),
                semantic_result.quality_gate.get("metrics"),
            )
            raise PackQualityGateError(
                f"Pack {pack_id} failed quality gate: {', '.join(semantic_result.quality_gate.get('failures', []))}"
            )

        artifacts = {
            **semantic_result.artifacts,
            "reports": semantic_result.reports,
            "quality_gate": semantic_result.quality_gate,
        }

        pack_record = self.repository.save_pack(
            {
                "pack_id": pack_id,
                "grade": metadata.get("grade"),
                "subject": metadata.get("subject"),
                "chapter": metadata.get("chapter"),
                "language": metadata.get("language"),
                "version": "1.0.0",
                "artifacts": artifacts,
                "generation_metadata": {
                    **metadata,
                    "pack_type": pack_type,
                    "compression": compression,
                    "include_media": include_media,
                    "quantize_embeddings": quantize_embeddings,
                    "pipeline": "semantic_educational_knowledge_pipeline_v1",
                },
                "quality_scores": {
                    "duplicate_ratio": semantic_result.quality_gate["metrics"]["duplicate_ratio"],
                    "average_chunk_length": semantic_result.quality_gate["metrics"]["average_chunk_length"],
                    "retrieval_precision": semantic_result.quality_gate["metrics"]["retrieval_precision"],
                    "quality_gate_passed": 1.0 if semantic_result.quality_gate["passed"] else 0.0,
                },
            }
        )

        archive_path = Path(pack_record["archive_path"])
        compressed_size = archive_path.stat().st_size / (1024 * 1024)
        pack_record["size_mb"] = compressed_size
        pack_record["chunk_count"] = len(processed_chunks)
        pack_record["checksum"] = pack_record.get("checksum")
        logger.info(f"Pack {pack_id} saved: {compressed_size:.2f}MB")
        return pack_record
    
    async def _compress_pack(self, pack_dir: Path, format: str = "gzip") -> Path:
        """Compress pack directory"""
        archive_name = pack_dir.name
        archive_path = pack_dir.parent / f"{archive_name}.tar.{format}"
        
        if format == "gzip":
            with tarfile.open(archive_path, "w:gz") as tar:
                tar.add(pack_dir, arcname=archive_name)
        elif format == "xz":
            with tarfile.open(archive_path, "w:xz") as tar:
                tar.add(pack_dir, arcname=archive_name)
        else:  # zstd or others
            with tarfile.open(archive_path, "w") as tar:
                tar.add(pack_dir, arcname=archive_name)
        
        logger.info(f"Pack compressed to {archive_path}")
        return archive_path
    
    def _quantize_embedding(self, embedding: List[float], bits: int = 8) -> List[int]:
        """Quantize float embeddings to reduce size"""
        if not embedding:
            return []
        
        # Find min/max
        min_val = min(embedding)
        max_val = max(embedding)
        range_val = max_val - min_val or 1.0
        
        # Quantize to 8-bit
        quantized = [int(((x - min_val) / range_val) * 255) for x in embedding]
        return quantized
    
    def _compute_checksum(self, data: dict) -> str:
        """Compute SHA256 checksum of pack data"""
        json_bytes = json.dumps(data, sort_keys=True).encode('utf-8')
        return hashlib.sha256(json_bytes).hexdigest()
    
    def get_pack_manifest(self, pack_id: str) -> Optional[dict]:
        """Get pack manifest"""
        return self.repository.load_manifest(pack_id)
    
    def list_packs(self) -> List[dict]:
        """List all available packs"""
        return self.repository.list_packs()
    
    def validate_pack_integrity(self, pack_id: str) -> Tuple[bool, str]:
        """Validate pack integrity"""
        valid, errors = self.repository.validate_pack(pack_id)
        if valid:
            return True, "Pack integrity verified"
        return False, "; ".join(errors)
