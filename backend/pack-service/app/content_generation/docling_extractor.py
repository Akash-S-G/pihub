from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from .models import StructuredBlock, StructuredDocument


HEADING_RE = re.compile(r"^(chapter\s+\d+|unit\s+\d+|\d+(\.\d+)*\s+.+|[A-Z][A-Z0-9 ,:;'-]{6,})$", re.I)
FORMULA_RE = re.compile(r"([A-Za-z][A-Za-z0-9_ ]{0,24}\s*[=∝]\s*[^.;\n]{1,80}|[A-Za-z]\s*=\s*[^.;\n]{1,80})")


def _dump_docling_model(value: Any) -> dict[str, Any]:
    if hasattr(value, "export_to_dict"):
        return value.export_to_dict()
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return value
    return {}


class DoclingPdfExtractor:
    """Extract structured textbook blocks with Docling, with a text fallback for tests/dev."""

    def extract(self, pdf_path: str | Path, metadata: dict[str, Any] | None = None) -> StructuredDocument:
        path = Path(pdf_path)
        metadata = dict(metadata or {})
        try:
            from docling.document_converter import DocumentConverter  # type: ignore

            result = DocumentConverter().convert(str(path))
            document = _dump_docling_model(result.document)
            blocks = self._blocks_from_docling(document)
            return StructuredDocument(
                source_path=str(path),
                title=str(document.get("name") or metadata.get("chapter") or path.stem),
                blocks=blocks,
                metadata={**metadata, "extractor": "docling", "docling_available": True},
            )
        except Exception as exc:
            blocks = self._fallback_blocks(path)
            return StructuredDocument(
                source_path=str(path),
                title=str(metadata.get("chapter") or path.stem),
                blocks=blocks,
                metadata={**metadata, "extractor": "fallback_text", "docling_available": False, "docling_error": str(exc)[:240]},
            )

    def extract_text(self, text: str, source_path: str = "inline", metadata: dict[str, Any] | None = None) -> StructuredDocument:
        return StructuredDocument(
            source_path=source_path,
            title=str((metadata or {}).get("chapter") or source_path),
            blocks=self._blocks_from_text(text),
            metadata={**dict(metadata or {}), "extractor": "inline_text", "docling_available": False},
        )

    def _blocks_from_docling(self, document: dict[str, Any]) -> list[StructuredBlock]:
        blocks: list[StructuredBlock] = []
        texts = document.get("texts") if isinstance(document.get("texts"), list) else []
        tables = document.get("tables") if isinstance(document.get("tables"), list) else []
        for index, item in enumerate(texts, start=1):
            text = self._text_from_docling_item(item)
            if not text:
                continue
            label = str(item.get("label") or item.get("type") or "").lower()
            block_type = "paragraph"
            level = 0
            if "section_header" in label or "title" in label or HEADING_RE.match(text):
                block_type = "heading" if not blocks else "subheading"
                level = 1 if block_type == "heading" else 2
            elif FORMULA_RE.search(text):
                block_type = "formula"
            elif str(item.get("enumerated", "")).lower() == "true":
                block_type = "list"
            blocks.append(self._block(index, block_type, text, level=level, metadata={"docling_label": label}))
        for index, table in enumerate(tables, start=len(blocks) + 1):
            rows = self._table_rows(table)
            if rows:
                blocks.append(self._block(index, "table", "\n".join(" | ".join(row) for row in rows), rows=rows))
        return blocks

    def _fallback_blocks(self, path: Path) -> list[StructuredBlock]:
        if path.suffix.lower() in {".txt", ".md"} and path.exists():
            return self._blocks_from_text(path.read_text(encoding="utf-8", errors="ignore"))
        return []

    def _blocks_from_text(self, text: str) -> list[StructuredBlock]:
        blocks: list[StructuredBlock] = []
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", str(text or "")) if part.strip()]
        for index, paragraph in enumerate(paragraphs, start=1):
            lines = [line.strip() for line in paragraph.splitlines() if line.strip()]
            first = lines[0] if lines else paragraph
            block_type = "paragraph"
            level = 0
            if len(lines) == 1 and (HEADING_RE.match(first) or len(first.split()) <= 8):
                block_type = "heading" if not blocks else "subheading"
                level = 1 if block_type == "heading" else 2
            elif FORMULA_RE.search(paragraph):
                block_type = "formula"
            elif self._looks_like_table(lines):
                block_type = "table"
            rows = [re.split(r"\s{2,}|\|", line) for line in lines] if block_type == "table" else []
            blocks.append(self._block(index, block_type, paragraph, level=level, rows=rows))
        return blocks

    @staticmethod
    def _text_from_docling_item(item: dict[str, Any]) -> str:
        for key in ("text", "orig", "content"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return re.sub(r"\s+", " ", value).strip()
        prov = item.get("prov")
        if isinstance(prov, list):
            return " ".join(str(part.get("text") or "").strip() for part in prov if isinstance(part, dict)).strip()
        return ""

    @staticmethod
    def _table_rows(table: dict[str, Any]) -> list[list[str]]:
        data = table.get("data") if isinstance(table.get("data"), dict) else table
        rows = data.get("table_cells") or data.get("cells") or []
        if not isinstance(rows, list):
            return []
        by_row: dict[int, list[tuple[int, str]]] = {}
        for cell in rows:
            if not isinstance(cell, dict):
                continue
            row = int(cell.get("start_row_offset_idx") or cell.get("row") or 0)
            col = int(cell.get("start_col_offset_idx") or cell.get("col") or 0)
            text = str(cell.get("text") or "").strip()
            by_row.setdefault(row, []).append((col, text))
        return [[text for _, text in sorted(values)] for _, values in sorted(by_row.items()) if values]

    @staticmethod
    def _looks_like_table(lines: list[str]) -> bool:
        if len(lines) < 2:
            return False
        table_lines = sum(1 for line in lines if "|" in line or len(re.split(r"\s{2,}", line)) >= 2)
        return table_lines >= 2

    @staticmethod
    def _block(index: int, block_type: str, text: str, level: int = 0, rows: list[list[str]] | None = None, metadata: dict[str, Any] | None = None) -> StructuredBlock:
        digest = hashlib.sha256(f"{index}:{block_type}:{text}".encode("utf-8")).hexdigest()[:12]
        return StructuredBlock(
            block_id=f"docling_{index}_{digest}",
            type=block_type,  # type: ignore[arg-type]
            text=text,
            level=level,
            rows=rows or [],
            metadata=metadata or {},
        )
