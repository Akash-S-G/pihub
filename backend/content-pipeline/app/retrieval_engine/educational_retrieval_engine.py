from __future__ import annotations

import re
from typing import Any

from shared.text_normalization import normalize_curriculum_name, normalize_language_code


class EducationalRetrievalEngine:
    """Hybrid semantic + lexical + curriculum-aware reranking for educational retrieval."""

    @staticmethod
    def _hit_field(hit: Any, name: str, default: Any = None) -> Any:
        if isinstance(hit, dict):
            return hit.get(name, default)
        return getattr(hit, name, default)

    def _tokenize(self, text: str) -> set[str]:
        return {
            token
            for token in re.findall(r"[\w\u0900-\u097F\u0C80-\u0CFF']+", text.lower())
            if token
        }

    @staticmethod
    def _word_count(text: str) -> int:
        return len(re.findall(r"[A-Za-z0-9\u0900-\u097F\u0C80-\u0CFF]+", text))

    def _semantic_score(self, raw_score: float | None) -> float:
        if raw_score is None:
            return 0.0
        return max(0.0, min(1.0, float(raw_score)))

    def _lexical_score(self, query: str, payload: dict[str, Any]) -> float:
        query_tokens = self._tokenize(query)
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
        payload_tokens = self._tokenize(payload_text)
        if not query_tokens or not payload_tokens:
            return 0.0
        return len(query_tokens & payload_tokens) / max(len(query_tokens), 1)

    def _chunk_type_score(self, query: str, payload: dict[str, Any]) -> float:
        chunk_type = str(payload.get("chunk_type", "")).lower()
        query_l = query.lower()
        text = str(payload.get("text", ""))
        if not chunk_type:
            return 0.0

        if chunk_type in {"metadata", "table_of_contents", "header_footer", "ocr_noise"}:
            return 0.0

        if any(k in query_l for k in ["define", "what is", "meaning"]) and chunk_type == "definition":
            return 1.0
        if any(k in query_l for k in ["formula", "equation"]) and chunk_type == "formula":
            return 1.0
        if any(k in query_l for k in ["example", "for example"]) and chunk_type == "example":
            return 0.9
        if any(k in query_l for k in ["experiment", "activity", "procedure"]) and chunk_type == "experiment":
            return 0.9
        if chunk_type == "formula":
            if self._word_count(text) >= 50 and len(text) >= 220:
                return 0.55
            return 0.15
        if chunk_type in {"definition", "explanation", "qa"}:
            return 0.6
        return 0.3

    def _topic_scores(
        self,
        payload: dict[str, Any],
        inferred_topics: list[str],
        prerequisites: list[str],
        related: list[str],
    ) -> tuple[float, str]:
        payload_topics = {str(t).lower() for t in (payload.get("topics") or [])}
        inferred = {t.lower() for t in inferred_topics}
        prereq = {t.lower() for t in prerequisites}
        rel = {t.lower() for t in related}

        if payload_topics & inferred:
            return 1.0, "exact_topic"
        if payload_topics & prereq:
            return 0.75, "prerequisite"
        if payload_topics & rel:
            return 0.6, "related"
        return 0.0, "none"

    @staticmethod
    def _contains_kannada(text: str) -> bool:
        return bool(re.search(r"[\u0C80-\u0CFF]", text or ""))

    def rank(
        self,
        query: str,
        hits: list[Any],
        limit: int,
        routed_filters: dict[str, Any],
        inferred_subject: str | None,
        inferred_topics: list[str],
        prerequisite_topics: list[str],
        related_topics: list[str],
    ) -> list[dict[str, Any]]:
        ranked: list[dict[str, Any]] = []

        target_subject = normalize_curriculum_name(str(routed_filters.get("subject") or inferred_subject or ""))
        target_chapter = normalize_curriculum_name(str(routed_filters.get("chapter") or ""))
        target_language = normalize_language_code(str(routed_filters.get("language") or ""))
        seen_signatures: set[str] = set()
        query_has_kannada = self._contains_kannada(query)

        for hit in hits:
            payload = self._hit_field(hit, "payload", {}) or {}
            raw_score = self._hit_field(hit, "score", None)
            text = str(payload.get("text", ""))
            signature = normalize_curriculum_name(text[:500])
            if signature and signature in seen_signatures:
                continue
            if signature:
                seen_signatures.add(signature)

            semantic = self._semantic_score(float(raw_score) if raw_score is not None else None)
            lexical = self._lexical_score(query, payload)
            chunk_type_score = self._chunk_type_score(query, payload)
            topic_score, topic_band = self._topic_scores(
                payload,
                inferred_topics=inferred_topics,
                prerequisites=prerequisite_topics,
                related=related_topics,
            )

            if str(payload.get("retrieval_source", "")).lower() == "local_hybrid":
                semantic = min(1.0, semantic + 0.08)

            if str(payload.get("chunk_type", "")).lower() in {"metadata", "table_of_contents", "header_footer", "ocr_noise"}:
                semantic = max(0.0, semantic - 0.18)

            payload_language = normalize_language_code(str(payload.get("language") or ""))
            if target_language and payload_language == target_language:
                semantic = min(1.0, semantic + 0.12)
            elif query_has_kannada and payload_language == "kn":
                semantic = min(1.0, semantic + 0.10)
            elif query_has_kannada and self._contains_kannada(text):
                semantic = min(1.0, semantic + 0.05)

            subject_match = 1.0 if target_subject and normalize_curriculum_name(str(payload.get("subject", ""))) == target_subject else 0.0
            chapter_match = 0.0
            payload_chapter = normalize_curriculum_name(str(payload.get("chapter", "")))
            if target_chapter and payload_chapter == target_chapter:
                chapter_match = 1.0
            elif payload_chapter and any(token in payload_chapter for token in self._tokenize(query)):
                chapter_match = 0.6

            educational = (
                0.40 * topic_score
                + 0.20 * chapter_match
                + 0.15 * subject_match
                + 0.25 * chunk_type_score
            )

            final_score = 0.35 * semantic + 0.35 * lexical + 0.30 * educational

            ranked.append(
                {
                    "id": str(self._hit_field(hit, "id", "")),
                    "score": final_score,
                    "vector_score": float(raw_score) if raw_score is not None else None,
                    "text": text,
                    "metadata": {k: v for k, v in payload.items() if k != "text"},
                    "ranking_debug": {
                        "semantic": semantic,
                        "lexical": lexical,
                        "educational": educational,
                        "topic_band": topic_band,
                        "subject_match": subject_match,
                        "chapter_match": chapter_match,
                        "chunk_type_score": chunk_type_score,
                    },
                }
            )

        ranked.sort(key=lambda item: item["score"], reverse=True)

        # Drop very low-signal results before truncating.
        filtered = [item for item in ranked if item["score"] >= 0.25]
        return filtered[:limit]
