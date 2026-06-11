from __future__ import annotations

import re
from collections import Counter
from typing import Any

from shared.text_normalization import normalize_curriculum_name


class ChunkMetadataBuilder:
    """Build normalized chunk metadata with educational fields."""

    STOPWORDS = {
        "the", "a", "an", "is", "are", "was", "were", "to", "of", "in", "on", "and", "or", "for", "with", "by",
        "this", "that", "these", "those", "it", "as", "at", "be", "from",
    }

    def build(
        self,
        text: str,
        base_metadata: dict[str, Any],
        section_title: str,
        chunk_type: str,
        topic_hint: str | None = None,
    ) -> dict[str, Any]:
        metadata = dict(base_metadata)
        metadata["section"] = normalize_curriculum_name(section_title)
        metadata["chunk_type"] = chunk_type
        metadata.setdefault("topic", normalize_curriculum_name(topic_hint or section_title))
        metadata.setdefault("language", "english")
        if metadata.get("subject"):
            metadata["subject"] = normalize_curriculum_name(str(metadata["subject"]))
        if metadata.get("chapter"):
            metadata["chapter"] = normalize_curriculum_name(str(metadata["chapter"]))
        if metadata.get("language"):
            metadata["language"] = normalize_curriculum_name(str(metadata["language"]))
        metadata.setdefault("difficulty", self._infer_difficulty(base_metadata))
        metadata.setdefault("keywords", self._extract_keywords(text))
        if "grade" in metadata and "difficulty" not in metadata:
            metadata["difficulty"] = f"grade_{metadata['grade']}"
        return metadata

    def _extract_keywords(self, text: str, limit: int = 8) -> list[str]:
        words = re.findall(r"[A-Za-z][A-Za-z0-9_\-]{2,}", text.lower())
        filtered = [word for word in words if word not in self.STOPWORDS]
        counts = Counter(filtered)
        return [word for word, _ in counts.most_common(limit)]

    def _infer_difficulty(self, metadata: dict[str, Any]) -> str:
        grade = metadata.get("grade")
        if grade is None:
            return "grade_unknown"
        return f"grade_{grade}"
