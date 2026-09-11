"""
Structured textbook ingestion — content-pipeline sole PDF processing service.

This module is the **authoritative, sole owner** of all raw PDF extraction
logic in the PIHUB backend. ``pack-service`` (:8030) does NOT perform PDF
parsing of any kind; it exclusively reads pre-generated packs written by
this pipeline to ``/shared/generated_pack``.

Extraction Tier Hierarchy (applied in order):
  Tier 1 — IBM Docling  (structured layout parsing, formula/table detection)
  Tier 2 — PyMuPDF fitz (native text layer extraction)
  Tier 3 — Tesseract OCR via fitz pixmap rendering (image-only / scanned PDFs)

Pipeline outputs per textbook:
  • Vector embeddings  → Qdrant collection
  • content.json       → /shared/generated_pack/<pack_id>/
  • quizzes.json       → /shared/generated_pack/<pack_id>/
  • flashcards.json    → /shared/generated_pack/<pack_id>/
  • summaries.json     → /shared/generated_pack/<pack_id>/

Directory structure expected for batch ingestion:
  content/
    class_6/
      science/
        photosynthesis.pdf
        respiration.pdf
      maths/
      social/
    class_7/
    ...
"""

from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any

from shared.config import get_settings
from shared.text_normalization import normalize_curriculum_name, normalize_language_code

import logging

from app.content_pipeline.educational_chunker import EducationalChunkerV2

logger = logging.getLogger(__name__)


class TextbookMetadataExtractor:
    """Extract curriculum metadata from file paths and content."""
    
    GRADE_MAP = {
        "class_6": 6, "class_7": 7, "class_8": 8, "class_9": 9, "class_10": 10,
        "grade_6": 6, "grade_7": 7, "grade_8": 8, "grade_9": 9, "grade_10": 10,
    }
    
    LANGUAGES = ["english", "kannada", "hindi", "marathi", "tamil", "telugu"]

    @classmethod
    def detect_language_from_text(cls, text: str) -> str:
        lower_text = text.lower()
        if any("\u0c80" <= char <= "\u0cff" for char in text):
            return "kn"
        if any("\u0900" <= char <= "\u097f" for char in text):
            return "hi"
        for language in cls.LANGUAGES:
            if language in lower_text:
                return normalize_language_code(language) or language
        return "en"
    
    @classmethod
    def extract_from_path(cls, file_path: Path) -> dict[str, Any]:
        """
        Extract metadata from file path structure.
        
        Example:
        content/class_7/science/photosynthesis.pdf
        →
        {
            "grade": 7,
            "subject": "science",
            "language": "english",  # default
            "textbook_name": "photosynthesis"
        }
        """
        parts = [p for p in file_path.parts]
        metadata: dict[str, Any] = {}
        subject_candidate: str | None = None
        filename = normalize_curriculum_name(file_path.stem)
        filename_tokens = set(re.findall(r"[a-z0-9]+", filename.lower()))

        language_aliases = {
            "en": {"english", "eng", "en"},
            "kn": {"kannada", "kan", "kannada_medium", "kn"},
            "hi": {"hindi", "hin", "hi"},
            "marathi": {"marathi", "mar"},
            "tamil": {"tamil", "tam"},
            "telugu": {"telugu", "tel"},
        }

        # Flexible grade extraction: handle 'class 8', 'grade 8', 'class_8', 'class8 part 1'
        for i, part in enumerate(parts):
            p = part.lower()
            # direct map
            if p in cls.GRADE_MAP:
                metadata["grade"] = cls.GRADE_MAP[p]
                # attempt to get subject from next part
                if i + 1 < len(parts):
                    next_part = parts[i + 1]
                    if ".pdf" not in next_part.lower():
                        metadata["subject"] = normalize_curriculum_name(next_part)
                    else:
                        subject_candidate = normalize_curriculum_name(next_part)
                break
            # regex match like 'class 8' or 'grade 8' or 'class8'
            m = re.search(r"(?:class|grade)\s*[_-]?(\d{1,2})", p)
            if m:
                try:
                    metadata["grade"] = int(m.group(1))
                except Exception:
                    pass
                if i + 1 < len(parts):
                    next_part = parts[i + 1]
                    if ".pdf" not in next_part.lower():
                        metadata["subject"] = normalize_curriculum_name(next_part)
                    else:
                        subject_candidate = normalize_curriculum_name(next_part)
                break

        # If subject still not found, prefer filename tokens and then path tokens.
        if "subject" not in metadata:
            SUBJECT_TOKENS = ["math", "maths", "mathematics", "science", "social", "social_science", "english", "kannada"]
            for token in SUBJECT_TOKENS:
                if token in filename_tokens:
                    if "math" in token:
                        metadata["subject"] = "mathematics"
                    elif "social" in token:
                        metadata["subject"] = "social_science"
                    else:
                        metadata["subject"] = normalize_curriculum_name(token)
                    break
            if "subject" not in metadata:
                for part in parts:
                    low = normalize_curriculum_name(part).lower()
                    if not low or "medium" in low:
                        continue
                    for token in SUBJECT_TOKENS:
                        if low == token or low.endswith(f"_{token}") or low.startswith(f"{token}_"):
                            if "math" in token:
                                metadata["subject"] = "mathematics"
                            elif "social" in token:
                                metadata["subject"] = "social_science"
                            else:
                                metadata["subject"] = normalize_curriculum_name(token)
                            break
                    if "subject" in metadata:
                        break

        if "subject" not in metadata and subject_candidate:
            metadata["subject"] = subject_candidate
        
        # Extract language if specified in path
        for lang in cls.LANGUAGES:
            if lang in str(file_path).lower():
                metadata["language"] = normalize_language_code(lang) or lang
                break

        # Default to English if not specified
        if "language" not in metadata:
            metadata["language"] = "en"
        
        # Extract textbook name / chapter from filename and sanitize
        # cleanup trailing dashes, separators, and trailing numbers
        name = re.sub(r"[\(\)\[\]]", "", filename)
        name = normalize_curriculum_name(name)
        metadata["textbook_name"] = name
        # Also expose a cleaned 'chapter' field for downstream use
        metadata["chapter"] = name

        for language, aliases in language_aliases.items():
            if any(alias in str(file_path).lower() for alias in aliases):
                metadata["language"] = normalize_language_code(language) or language
                break
        
        return metadata

    @classmethod
    def merge_text_metadata(cls, metadata: dict[str, Any], text: str) -> dict[str, Any]:
        merged = dict(metadata)
        language = merged.get("language")
        if not language or normalize_language_code(language) == "en":
            merged["language"] = cls.detect_language_from_text(text)
        # Clean chapter trailing characters
        if merged.get("chapter"):
            merged["chapter"] = normalize_curriculum_name(str(merged.get("chapter")))
        if merged.get("subject"):
            merged["subject"] = normalize_curriculum_name(str(merged.get("subject")))
        if merged.get("language"):
            merged["language"] = normalize_language_code(str(merged.get("language"))) or normalize_curriculum_name(str(merged.get("language")))
        if merged.get("textbook_name"):
            merged["textbook_name"] = normalize_curriculum_name(str(merged.get("textbook_name")))
        return merged


class EducationalChunkDetector:
    """Detect educational boundaries for semantic chunking."""
    
    # Patterns to detect chapter/section boundaries
    CHAPTER_PATTERNS = [
        r"^chapter\s+\d+",
        r"^unit\s+\d+",
        r"^lesson\s+\d+",
        r"^section\s+\d+",
        r"^topic\s+\d+",
        r"^ಅಧ್ಯಾಯ\s+\d+",
        r"^ಪಾಠ\s+\d+",
        r"^exercise",
        r"^questions",
    ]
    
    SECTION_PATTERNS = [
        r"^[a-z0-9\.\s]+\n(?=[A-Z])",  # Uppercase after newline
        r"^[0-9]+\.[0-9]+\s+",  # Numbered sections
    ]

    CHAPTER_KEYWORDS = ("chapter", "unit", "lesson", "topic")
    SECTION_KEYWORDS = ("exercise", "example", "activity", "question", "questions", "solve", "practice")
    MULTILINGUAL_SECTION_KEYWORDS = ("ಅಭ್ಯಾಸ", "ಉದಾಹರಣೆ", "ಚಟುವಟಿಕೆ", "ಪ್ರಶ್ನೆ", "ಪರಿಹಾರ", "ಅಭ್ಯಾಸಗಳು")
    
    @classmethod
    def detect_chapters(cls, text: str) -> list[dict[str, Any]]:
        """
        Detect chapter boundaries in text.
        
        Returns:
        [
            {
                "title": "Chapter 1: Photosynthesis",
                "start": 0,
                "end": 500,
                "topics": ["photosynthesis", "chlorophyll", ...]
            }
        ]
        """
        chapters: list[dict[str, Any]] = []
        lines = text.split("\n")
        
        current_chapter: dict[str, Any] | None = None
        current_pos = 0
        
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            
            if not line_stripped:
                current_pos += len(line) + 1
                continue

            # Check if line matches chapter pattern
            if cls._is_chapter_heading(line_stripped):
                # Save previous chapter
                if current_chapter:
                    current_chapter["end"] = current_pos
                    chapters.append(current_chapter)
                
                # Start new chapter
                current_chapter = {
                    "title": line_stripped,
                    "start": current_pos,
                    "topics": cls._extract_topics(line_stripped),
                    "sections": [],
                }
            elif current_chapter and cls._is_section_heading(line_stripped):
                current_chapter.setdefault("sections", []).append({
                    "title": line_stripped,
                    "start": current_pos,
                    "topics": cls._extract_topics(line_stripped),
                })
            
            current_pos += len(line) + 1  # +1 for newline
        
        # Save last chapter
        if current_chapter:
            current_chapter["end"] = current_pos
            chapters.append(current_chapter)

        if not chapters:
            chapters.append({
                "title": "Document",
                "start": 0,
                "end": len(text),
                "topics": cls._extract_topics(text[:120]),
                "sections": [],
            })
        
        return chapters
    
    @classmethod
    def _is_chapter_heading(cls, text: str) -> bool:
        """Check if text matches chapter heading patterns."""
        for pattern in cls.CHAPTER_PATTERNS:
            if re.match(pattern, text, re.IGNORECASE):
                return True
        if len(text.split()) <= 8 and text and text[0].isupper() and text.endswith(":"):
            return True
        return False

    @classmethod
    def _is_section_heading(cls, text: str) -> bool:
        lowered = text.lower()
        if lowered.startswith(cls.SECTION_KEYWORDS):
            return True
        if text.startswith(cls.MULTILINGUAL_SECTION_KEYWORDS):
            return True
        if re.match(r"^[0-9]+(\.[0-9]+)*\s+", text):
            return True
        if len(text.split()) <= 10 and text and text[0].isupper() and text.endswith(":"):
            return True
        return False
    
    @classmethod
    def _extract_topics(cls, heading: str) -> list[str]:
        """Extract potential topics from heading."""
        # Remove numbers and common prefixes
        cleaned = re.sub(r"^(chapter|unit|lesson|section|exercise|question|topic|unit)\s+\d+:?\s*", "", heading, flags=re.IGNORECASE)
        
        # Split on common delimiters
        topics = re.split(r"[;,/\-]", cleaned)
        
        # Clean up and filter
        return [t.strip().lower() for t in topics if t.strip() and len(t.strip()) > 3]


class EducationalChunker:
    """
    Semantic chunking for educational content.
    
    DO NOT use fixed-size character chunks.
    Chunk by:
    - chapter
    - section  
    - paragraph
    """
    
    def __init__(self, chapter_separator: str = "\n\n", min_chunk_size: int = 100, max_chunk_size: int = 1200):
        self.chapter_separator = chapter_separator
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
    
    def chunk_educational(self, text: str, metadata: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Chunk text using educational semantic boundaries.
        
        Returns chunks with enriched metadata.
        """
        # Detect chapters first
        chapters = EducationalChunkDetector.detect_chapters(text)
        
        chunks: list[dict[str, Any]] = []
        
        for chapter in chapters:
            chapter_text = text[chapter["start"]:chapter["end"]]

            section_title = chapter["title"]
            paragraphs = [paragraph.strip() for paragraph in re.split(r"\n\s*\n", chapter_text) if paragraph.strip()]

            buffer: list[str] = []
            buffer_length = 0

            def flush_buffer(current_section: str | None = None) -> None:
                nonlocal buffer, buffer_length
                if not buffer:
                    return
                chunk_text = "\n\n".join(buffer).strip()
                if len(chunk_text) >= self.min_chunk_size or not chunks:
                    chunks.append({
                        "text": chunk_text,
                        "metadata": {
                            **metadata,
                            "chapter": chapter["title"],
                            "section": current_section or section_title,
                            "topics": chapter.get("topics", []),
                        },
                    })
                buffer = []
                buffer_length = 0

            for paragraph in paragraphs:
                lines = paragraph.splitlines()
                first_line = lines[0].strip() if lines else ""
                is_section = EducationalChunkDetector._is_section_heading(first_line)
                if is_section:
                    flush_buffer(section_title)
                    section_title = first_line
                    remaining = "\n".join(lines[1:]).strip()
                    if remaining:
                        buffer.append(remaining)
                        buffer_length = len(remaining)
                    continue

                if buffer_length + len(paragraph) + 2 > self.max_chunk_size and buffer:
                    flush_buffer(section_title)

                buffer.append(paragraph)
                buffer_length += len(paragraph) + 2

            flush_buffer(section_title)
        
        return chunks


class StructuredTextbookIngest:
    """Main API for structured textbook ingestion on content-pipeline.

    Enforces a strict 3-tier PDF extraction hierarchy:
      Tier 1 — IBM Docling   : primary structured parser (layout, tables, formulas).
      Tier 2 — PyMuPDF fitz  : native text-layer extraction fallback.
      Tier 3 — Tesseract OCR : OCR fallback for scanned / image-only PDFs.

    The ``extract_text_from_pdf`` method attempts each tier in order and
    returns on the first tier that produces >40 characters of text.  The
    ``extraction_tier`` attribute on the returned metadata records which
    tier was ultimately used ("docling" | "pymupdf" | "tesseract" | "none").

    NOTE: pack-service (:8030) must NEVER call this class or import fitz /
    docling.  All PDF processing happens here and finished artifacts are
    written to /shared/generated_pack for pack-service to serve.
    """

    def __init__(self):
        settings = get_settings()
        self.metadata_extractor = TextbookMetadataExtractor()
        self.chunker = EducationalChunker()
        self.semantic_chunker = EducationalChunkerV2()
        self.enable_semantic_educational_chunking = settings.enable_semantic_educational_chunking

    def extract_text_from_pdf(self, file_path: Path) -> tuple[str, str]:
        """Extract text from PDF using the 3-tier hierarchy.

        Returns:
            (text, extraction_tier) where extraction_tier is one of
            ``"docling"`` | ``"pymupdf"`` | ``"tesseract"`` | ``"none"``.

        Tier 1 — IBM Docling
            Full layout analysis: detects headings, tables, formulas, and
            reading order.  Preferred for well-structured digital textbooks.

        Tier 2 — PyMuPDF (fitz) native text layer
            Fast native text extraction from PDF internal text streams.
            Used when Docling is unavailable or returns <40 chars.

        Tier 3 — Tesseract OCR (via fitz pixmap rendering)
            Renders each page to a 2× resolution image and runs Tesseract.
            Used for scanned / image-only PDFs where the text layer is absent.
        """
        # ── Tier 1: IBM Docling ──────────────────────────────────────────────
        docling_text = self._extract_text_with_docling(file_path)
        if docling_text and len(docling_text) > 40:
            logger.debug("[Tier1/Docling] extracted %d chars from %s", len(docling_text), file_path.name)
            print(f"[ingest] tier=docling file={file_path.name} chars={len(docling_text)}")
            return docling_text, "docling"

        try:
            import fitz

            document = fitz.open(str(file_path))

            # ── Tier 2: PyMuPDF native text layer ────────────────────────────
            pages: list[str] = []
            for page in document:
                page_text = page.get_text("text").strip()
                if page_text:
                    pages.append(page_text)

            extracted = "\n".join(pages).strip()
            logger.debug("[Tier2/PyMuPDF] extracted %d chars from %s", len(extracted), file_path.name)
            print(f"[ingest] tier=pymupdf file={file_path.name} chars={len(extracted)}")
            if extracted and len(extracted) > 40:
                return extracted, "pymupdf"

            # ── Tier 3: Tesseract OCR (image-only / scanned PDFs) ────────────
            try:
                import pytesseract
                from PIL import Image
            except Exception:
                logger.debug("[Tier3/Tesseract] unavailable for %s; returning Tier 2 result", file_path.name)
                return extracted, "pymupdf" if extracted else "none"

            ocr_pages: list[str] = []
            for page in document:
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                image = Image.open(io.BytesIO(pix.tobytes("png")))
                ocr_text = pytesseract.image_to_string(image).strip()
                if ocr_text:
                    ocr_pages.append(ocr_text)

            ocr_result = "\n".join(ocr_pages).strip()
            logger.debug("[Tier3/Tesseract] extracted %d chars from %s", len(ocr_result), file_path.name)
            print(f"[ingest] tier=tesseract file={file_path.name} chars={len(ocr_result)}")
            if ocr_result:
                return ocr_result, "tesseract"
            return extracted, "pymupdf" if extracted else "none"
        except Exception as exc:
            raise RuntimeError(f"Unable to extract text from {file_path.name}: {exc}") from exc

    def extract_images(
        self,
        file_path: Path,
        *,
        min_width: int = 200,
        min_height: int = 200,
        min_area: int = 40_000,
    ) -> list[dict[str, Any]]:
        """Extract 'important' raster images from a PDF and persist them.

        Only images above the size thresholds are kept (skips tiny icons,
        rule lines and decorative glyphs). Each image is rendered to PNG
        under ``<upload_dir>/images/<book>/`` and a manifest entry is
        returned with page number, pixel size and any nearby caption.

        The manifest can be attached to chunk/section metadata so retrieval
        can surface the relevant figure alongside text.
        """
        try:
            import fitz
        except Exception as exc:  # pragma: no cover - fitz optional at import
            logger.debug("fitz unavailable, skipping image extraction: %s", exc)
            return []

        settings = get_settings()
        book = file_path.stem
        image_dir = Path(settings.upload_dir) / "images" / book
        image_dir.mkdir(parents=True, exist_ok=True)

        # Pre-scan pages for caption text to associate with images.
        doc = fitz.open(str(file_path))
        page_texts = [page.get_text("text") for page in doc]

        manifest: list[dict[str, Any]] = []
        seen_xrefs: set[int] = set()
        order = 0
        for page_index, page in enumerate(doc):
            for img in page.get_images(full=True):
                xref = img[0]
                if xref in seen_xrefs:
                    continue
                seen_xrefs.add(xref)
                try:
                    pix = fitz.Pixmap(doc, xref)
                    if pix.width < min_width or pix.height < min_height:
                        continue
                    if pix.width * pix.height < min_area:
                        continue
                    if pix.alpha:
                        pix = fitz.Pixmap(pix, alpha=False)
                    caption = self._nearest_caption(page_texts, page_index)
                    order += 1
                    fname = f"p{page_index + 1}_{order}.png"
                    pix.save(str(image_dir / fname))
                    manifest.append({
                        "filename": fname,
                        "path": str(image_dir / fname),
                        "page": page_index + 1,
                        "width": pix.width,
                        "height": pix.height,
                        "caption": caption,
                        "book": book,
                    })
                except Exception as exc:  # skip unreadable image xrefs
                    logger.debug("Skipping image xref %s in %s: %s", xref, file_path.name, exc)
                    continue
        doc.close()
        print(f"[ingest] images_extracted {file_path.name} count={len(manifest)}")
        return manifest

    @staticmethod
    def _nearest_caption(page_texts: list[str], page_index: int) -> str:
        """Find a figure caption on this/next page near the bottom/top."""
        window = [t for t in page_texts[max(0, page_index - 1): page_index + 2] if t]
        joined = "\n".join(window)
        m = re.search(r"(figure\s+\d+[\.:]?\s*[^\n]{0,120})", joined, re.IGNORECASE)
        return m.group(1).strip() if m else ""

    def _extract_text_with_docling(self, file_path: Path) -> str:
        """Tier 1 extractor: IBM Docling structured layout parser.

        Produces Markdown-structured text preserving headings, tables, and
        formulas.  Returns an empty string on any failure so the caller can
        fall through to Tier 2 (PyMuPDF).
        """
        try:
            from docling.document_converter import DocumentConverter  # type: ignore

            result = DocumentConverter().convert(str(file_path))
            document = result.document
            if hasattr(document, "export_to_markdown"):
                return str(document.export_to_markdown()).strip()
            if hasattr(document, "export_to_text"):
                return str(document.export_to_text()).strip()
        except Exception as exc:
            logger.debug("[Tier1/Docling] unavailable for %s: %s", file_path.name, exc)
        return ""

    def ingest_pdf(self, file_path: Path) -> list[dict[str, Any]]:
        """Ingest a PDF file directly from disk.

        Applies the 3-tier extraction hierarchy and passes the extracted text
        and tier label into ``ingest_from_path`` for metadata tagging.
        """
        raw_text, extraction_tier = self.extract_text_from_pdf(file_path)
        return self.ingest_from_path(file_path, raw_text, extraction_tier=extraction_tier)

    def ingest_directory(self, directory: Path, recursive: bool = True) -> list[dict[str, Any]]:
        """Ingest all PDFs from a directory tree."""
        pattern = "**/*.pdf" if recursive else "*.pdf"
        chunks: list[dict[str, Any]] = []
        for file_path in sorted(directory.glob(pattern)):
            chunks.extend(self.ingest_pdf(file_path))
        return chunks
    
    def ingest_from_path(
        self,
        file_path: Path,
        text_content: str,
        *,
        extraction_tier: str = "unknown",
    ) -> list[dict[str, Any]]:
        """
        Full ingestion pipeline:
        1. Extract metadata from path
        2. Detect chapters
        3. Create semantic chunks with extraction tier tagged in metadata

        Args:
            file_path: Source PDF path (used for metadata extraction only).
            text_content: Pre-extracted text from extract_text_from_pdf().
            extraction_tier: Which tier produced the text
                ("docling" | "pymupdf" | "tesseract" | "none" | "unknown").
        """
        # Extract metadata from path and merge with text-derived metadata
        metadata = self.metadata_extractor.merge_text_metadata(
            self.metadata_extractor.extract_from_path(file_path), text_content
        )
        metadata["extraction_tier"] = extraction_tier

        # Chunk educational content. Keep legacy chunker available for compatibility.
        if self.enable_semantic_educational_chunking:
            chunks = self.semantic_chunker.chunk_educational(text_content, metadata)
        else:
            chunks = self.chunker.chunk_educational(text_content, metadata)

        # Extract and persist important figures; tag chunks whose text
        # references a figure with that image (caption-based association,
        # since the section chunker does not track page numbers).
        image_manifest = self.extract_images(file_path)
        if image_manifest:
            metadata.setdefault("images", [m["filename"] for m in image_manifest])
            for chunk in chunks:
                ctext = chunk.get("text", "")
                linked = [
                    img["filename"]
                    for img in image_manifest
                    if img["caption"] and img["caption"][:25].lower() in ctext.lower()
                ]
                if linked:
                    chunk.setdefault("metadata", {})["images"] = linked

        logger.debug("Ingested %s -> extracted_text_len=%d, chunks=%d", file_path.name, len(text_content or ""), len(chunks))
        print(f"[ingest] chunking_result {file_path.name} extracted_len={len(text_content or '')} chunk_count={len(chunks)}")
        if chunks:
            # log first chunk sizes for diagnostics
            first_len = len(chunks[0].get("text", ""))
            logger.debug("First chunk length: %d", first_len)
            print(f"[ingest] first_chunk_length {file_path.name} {first_len}")

        return chunks


# Example usage
if __name__ == "__main__":
    # Test metadata extraction
    test_path = Path("content/class_7/science/photosynthesis.pdf")
    extractor = TextbookMetadataExtractor()
    print("Extracted metadata:", extractor.extract_from_path(test_path))
    
    # Test chapter detection
    sample_text = """
    Chapter 1: Photosynthesis
    
    Photosynthesis is the process by which plants make food.
    
    Section 1.1: What is Photosynthesis
    
    It occurs in the chloroplasts of plant cells.
    
    Chapter 2: Respiration
    
    Respiration is the opposite of photosynthesis.
    """
    
    detector = EducationalChunkDetector()
    chapters = detector.detect_chapters(sample_text)
    print("\nDetected chapters:", chapters)
    
    # Test chunking
    ingest = StructuredTextbookIngest()
    chunks = ingest.ingest_from_path(test_path, sample_text)
    print(f"\nCreated {len(chunks)} chunks")
    for i, chunk in enumerate(chunks, 1):
        print(f"\nChunk {i}:")
        print(f"  Text: {chunk['text'][:100]}...")
        print(f"  Metadata: {chunk['metadata']}")
