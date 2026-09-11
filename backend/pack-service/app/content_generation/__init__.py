"""Gemma-backed content generation helpers for pre-extracted text blocks.

PDF extraction has been removed from pack-service.
All PDF ingestion is handled exclusively by content-pipeline (:8001),
which writes finished packs to /shared/generated_pack.
pack-service (:8030) reads those pre-generated artifacts — it never
touches raw PDF files or imports docling/fitz directly.
"""

from .artifact_generator import GemmaArtifactGenerator
from .models import StructuredBlock, StructuredDocument, StructuredSection
from .section_builder import SectionBuilder

__all__ = [
    "GemmaArtifactGenerator",
    "SectionBuilder",
    "StructuredBlock",
    "StructuredDocument",
    "StructuredSection",
]
