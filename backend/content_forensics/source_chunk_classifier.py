from __future__ import annotations

import re
from enum import Enum
from typing import Any


class SourceChunkCategory(str, Enum):
    CONCEPT_EXPLANATION = "CONCEPT_EXPLANATION"
    DEFINITION = "DEFINITION"
    WORKED_EXAMPLE = "WORKED_EXAMPLE"
    FORMULA_EXPLANATION = "FORMULA_EXPLANATION"
    ACTIVITY = "ACTIVITY"
    EXERCISE = "EXERCISE"
    ASSESSMENT = "ASSESSMENT"
    QUESTION = "QUESTION"
    GLOSSARY = "GLOSSARY"
    SUMMARY = "SUMMARY"
    TABLE_OF_CONTENTS = "TABLE_OF_CONTENTS"
    INDEX = "INDEX"
    METADATA = "METADATA"
    OCR_NOISE = "OCR_NOISE"
    OTHER = "OTHER"


FORMULA_RE = re.compile(r"(?:[A-Za-z][A-Za-z\s]{0,35}|[A-Za-z])\s*(?:=|<|>|≤|≥|≈|∝)\s*[A-Za-z0-9πθ°%+\-*/×÷^().,\s]{1,110}")
DEFINITION_RE = re.compile(r"\b(?:is|are|means|refers to|is called|are called|can be defined as)\b", re.I)
EXPLANATION_RE = re.compile(
    r"\b(?:because|therefore|hence|so that|this means|this shows|for example|in other words|as a result|depends on|caused by|leads to)\b",
    re.I,
)
QUESTION_RE = re.compile(r"\?\s*$|^\s*(?:what|why|how|when|where|which|explain|describe|discuss|find|calculate|state)\b", re.I)


class SourceChunkClassifier:
    def classify(self, chunk: dict[str, Any]) -> dict[str, Any]:
        text = str(chunk.get("text") or "")
        metadata = chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else {}
        category = self.category(text, metadata)
        return {
            "chunk_id": str(chunk.get("chunk_id") or ""),
            "category": category.value,
            "grade": metadata.get("grade"),
            "subject": metadata.get("subject"),
            "chapter": metadata.get("chapter"),
            "length_chars": len(text),
            "length_words": len(re.findall(r"[A-Za-z0-9]+", text)),
            "preview": re.sub(r"\s+", " ", text).strip()[:240],
        }

    def category(self, text: str, metadata: dict[str, Any] | None = None) -> SourceChunkCategory:
        metadata = metadata or {}
        lower = text.lower()
        word_count = len(re.findall(r"[A-Za-z0-9]+", text))
        alpha_ratio = sum(1 for char in text if char.isalpha()) / max(1, len(text))
        content_type = str(metadata.get("content_type") or "").lower()

        if not text.strip() or word_count < 4:
            return SourceChunkCategory.OCR_NOISE
        if alpha_ratio < 0.35 or self._looks_like_ocr_noise(text):
            return SourceChunkCategory.OCR_NOISE
        if self._looks_like_toc(text):
            return SourceChunkCategory.TABLE_OF_CONTENTS
        if self._looks_like_index(text):
            return SourceChunkCategory.INDEX
        if self._looks_like_metadata(text):
            return SourceChunkCategory.METADATA
        if "summary" in lower[:100] or "what we have learnt" in lower[:180] or content_type == "summary":
            return SourceChunkCategory.SUMMARY
        if "glossary" in lower[:100] or self._looks_like_glossary(text):
            return SourceChunkCategory.GLOSSARY
        if any(marker in lower for marker in ("worked example", "solution", "solved example")) or (
            any(marker in lower for marker in ("therefore", "hence", "step")) and FORMULA_RE.search(text)
        ):
            return SourceChunkCategory.WORKED_EXAMPLE
        if FORMULA_RE.search(text):
            if EXPLANATION_RE.search(text) or word_count >= 35:
                return SourceChunkCategory.FORMULA_EXPLANATION
            return SourceChunkCategory.QUESTION if QUESTION_RE.search(text) else SourceChunkCategory.OTHER
        if "assessment" in lower[:120] or "test yourself" in lower[:160]:
            return SourceChunkCategory.ASSESSMENT
        if "exercise" in lower[:120] or "practice" in lower[:120]:
            return SourceChunkCategory.EXERCISE
        if "activity" in lower[:120] or "try this" in lower[:120] or "let us do" in lower[:160]:
            return SourceChunkCategory.ACTIVITY
        if QUESTION_RE.search(text) or self._question_density(text) >= 0.25:
            return SourceChunkCategory.QUESTION
        if DEFINITION_RE.search(text) and word_count >= 18:
            return SourceChunkCategory.DEFINITION
        if word_count >= 45 and EXPLANATION_RE.search(text):
            return SourceChunkCategory.CONCEPT_EXPLANATION
        if word_count >= 70 and self._sentence_count(text) >= 3:
            return SourceChunkCategory.CONCEPT_EXPLANATION
        return SourceChunkCategory.OTHER

    @staticmethod
    def tutor_ready(category: str, text: str) -> bool:
        if category in {
            SourceChunkCategory.CONCEPT_EXPLANATION.value,
            SourceChunkCategory.DEFINITION.value,
            SourceChunkCategory.WORKED_EXAMPLE.value,
            SourceChunkCategory.FORMULA_EXPLANATION.value,
            SourceChunkCategory.SUMMARY.value,
        }:
            return True
        return False

    @staticmethod
    def quality_label(category: str, text: str) -> str:
        word_count = len(re.findall(r"[A-Za-z0-9]+", text))
        sentences = SourceChunkClassifier._sentence_count(text)
        if category in {SourceChunkCategory.OCR_NOISE.value, SourceChunkCategory.METADATA.value, SourceChunkCategory.TABLE_OF_CONTENTS.value, SourceChunkCategory.INDEX.value}:
            return "Unusable"
        if category in {SourceChunkCategory.ACTIVITY.value, SourceChunkCategory.EXERCISE.value, SourceChunkCategory.QUESTION.value, SourceChunkCategory.ASSESSMENT.value, SourceChunkCategory.OTHER.value}:
            return "Poor" if word_count < 80 else "Acceptable"
        if word_count >= 100 and sentences >= 4 and EXPLANATION_RE.search(text):
            return "Excellent"
        if word_count >= 60 and sentences >= 2:
            return "Good"
        return "Acceptable"

    @staticmethod
    def _sentence_count(text: str) -> int:
        return len([item for item in re.split(r"(?<=[.!?])\s+", text.strip()) if item])

    @staticmethod
    def _question_density(text: str) -> float:
        sentences = [item for item in re.split(r"(?<=[.!?])\s+", text.strip()) if item]
        if not sentences:
            return 0.0
        questions = sum(1 for item in sentences if "?" in item or QUESTION_RE.search(item))
        return questions / len(sentences)

    @staticmethod
    def _looks_like_toc(text: str) -> bool:
        lower = text.lower()
        if "contents" in lower[:80] or "table of contents" in lower[:120]:
            return True
        dotted_lines = len(re.findall(r"\.{3,}\s*\d+", text))
        chapter_lines = len(re.findall(r"chapter\s+\d+", lower))
        return dotted_lines >= 3 or chapter_lines >= 5

    @staticmethod
    def _looks_like_index(text: str) -> bool:
        lower = text.lower()
        if "index" in lower[:80]:
            return True
        comma_pages = len(re.findall(r"\b[A-Za-z][A-Za-z\s-]{2,20},\s*\d+", text))
        return comma_pages >= 5

    @staticmethod
    def _looks_like_metadata(text: str) -> bool:
        lower = text.lower()
        return any(marker in lower for marker in ("isbn", "copyright", "published by", "all rights reserved", "national council of educational"))

    @staticmethod
    def _looks_like_glossary(text: str) -> bool:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return False
        colon_lines = sum(1 for line in lines if re.match(r"^[A-Za-z][A-Za-z\s-]{2,40}\s*[:\-]\s*.{12,}", line))
        return colon_lines >= 3

    @staticmethod
    def _looks_like_ocr_noise(text: str) -> bool:
        if re.search(r"(?:[a-z]\s){5,}[a-z]", text.lower()):
            return True
        if len(re.findall(r"[^\w\s.,;:!?()\-+=<>≤≥≈∝×÷°%πθ]", text)) / max(1, len(text)) > 0.08:
            return True
        return False
