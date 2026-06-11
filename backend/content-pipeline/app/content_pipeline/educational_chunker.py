from __future__ import annotations

import re
from typing import Any

from app.content_pipeline.chunk_metadata_builder import ChunkMetadataBuilder
from app.content_pipeline.concept_boundary_detector import ConceptBoundaryDetector
from app.content_pipeline.educational_classifier import EducationalClassifier
from app.content_pipeline.extraction_cleaner import clean_raw_text, repair_chunks
from app.content_pipeline.formula_preserver import FormulaPreserver
from app.content_pipeline.paragraph_merger import ParagraphMerger
from app.content_pipeline.section_parser import ParsedSection, SectionParser


class EducationalChunkerV2:
    """Semantic educational chunker that preserves formulas and pedagogical blocks."""

    def __init__(self, min_chunk_chars: int = 180, max_chunk_chars: int = 1300) -> None:
        self.min_chunk_chars = min_chunk_chars
        self.max_chunk_chars = max_chunk_chars
        self.section_parser = SectionParser()
        self.paragraph_merger = ParagraphMerger(min_chars=120)
        self.classifier = EducationalClassifier()
        self.formula_preserver = FormulaPreserver()
        self.boundary_detector = ConceptBoundaryDetector()
        self.metadata_builder = ChunkMetadataBuilder()

    def chunk_educational(self, text: str, metadata: dict[str, Any]) -> list[dict[str, Any]]:
        cleaned_text = clean_raw_text(text)
        sections = self.section_parser.parse(cleaned_text)
        chunks: list[dict[str, Any]] = []

        for section in sections:
            section_chunks = self._chunk_section(section, metadata)
            chunks.extend(section_chunks)

        repaired, _ = repair_chunks(chunks)
        return repaired

    def _chunk_section(self, section: ParsedSection, base_metadata: dict[str, Any]) -> list[dict[str, Any]]:
        raw_paragraphs = [p.strip() for p in re.split(r"\n\s*\n", section.content) if p.strip()]
        paragraphs = self.paragraph_merger.merge(raw_paragraphs)
        section_chunks: list[dict[str, Any]] = []
        current: list[str] = []
        current_len = 0

        def flush() -> None:
            nonlocal current, current_len
            if not current:
                return
            text = "\n\n".join(current).strip()
            if not text:
                current, current_len = [], 0
                return
            chunk_type = self.classifier.classify(text)
            metadata = self.metadata_builder.build(
                text=text,
                base_metadata=base_metadata,
                section_title=section.title,
                chunk_type=chunk_type,
                topic_hint=section.title,
            )
            section_chunks.append({"text": text, "metadata": metadata})
            current, current_len = [], 0

        for paragraph in paragraphs:
            paragraph_len = len(paragraph)
            force_atomic = self.formula_preserver.is_formula_block(paragraph) or self.boundary_detector.is_boundary_start(paragraph)

            if force_atomic:
                flush()
                atomic_type = self.boundary_detector.boundary_label(paragraph) or self.classifier.classify(paragraph)
                atomic_meta = self.metadata_builder.build(
                    text=paragraph,
                    base_metadata=base_metadata,
                    section_title=section.title,
                    chunk_type=atomic_type,
                    topic_hint=section.title,
                )
                section_chunks.append({"text": paragraph, "metadata": atomic_meta})
                continue

            if current and (current_len + paragraph_len + 2) > self.max_chunk_chars:
                flush()

            current.append(paragraph)
            current_len += paragraph_len + 2

            if current_len >= self.min_chunk_chars and self.boundary_detector.is_boundary_start(paragraph):
                flush()

        flush()
        return section_chunks
