from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any


OCR_PATTERNS = (
    "\uf03d",
    "\uf0b4",
    "\uf0a7",
    "\uf0d8",
    "\uf0fc",
    "\u00ad",
    "\ufffd",
    "\x08",
)

HEADER_FOOTER_PATTERNS = (
    re.compile(r"^reprint\s+\d{4}\s*-\s*\d{2}$", re.I),
    re.compile(r"^(ganita prakash|curiosity|mathematics|science)\s*\|\s*grade\s+\d+$", re.I),
    re.compile(r"^chapter\s+\d+$", re.I),
    re.compile(r"^fig\.?\s*\d+(\.\d+)?$", re.I),
    re.compile(r"^table\s+\d+(\.\d+)?$", re.I),
)


@dataclass(frozen=True)
class CleanDecision:
    keep: bool
    reason: str
    cleaned_text: str


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def content_hash(text: str) -> str:
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


def word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9]+", text or ""))


def is_page_number(text: str) -> bool:
    return bool(re.fullmatch(r"(page\s*(no\.?)?\s*)?\d{1,4}", text.strip(), flags=re.I))


def is_header_footer(text: str) -> bool:
    stripped = text.strip()
    return any(pattern.fullmatch(stripped) for pattern in HEADER_FOOTER_PATTERNS)


def is_formula_only(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) > 180:
        return False
    symbols = sum(1 for char in stripped if char in "=+-×÷*/^√∠∆π≤≥<>°")
    words = word_count(stripped)
    letters = sum(1 for char in stripped if char.isalpha())
    return symbols >= 1 and words <= 10 and letters < 35


def is_table_fragment(text: str) -> bool:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 4:
        return False
    short_lines = sum(1 for line in lines if len(line) <= 28)
    numeric_lines = sum(1 for line in lines if re.search(r"\d", line))
    return short_lines / len(lines) > 0.62 and numeric_lines / len(lines) > 0.30


def is_ocr_noise(text: str) -> bool:
    stripped = text.strip()
    if any(pattern in stripped for pattern in OCR_PATTERNS):
        return True
    if len(stripped) >= 12 and re.search(r"(?:[A-Za-z]\s){5,}[A-Za-z]", stripped):
        return True
    if len(stripped) >= 20:
        printable = sum(1 for char in stripped if char.isprintable())
        alpha = sum(1 for char in stripped if char.isalpha())
        digit_space = sum(1 for char in stripped if char.isdigit() or char.isspace())
        symbolish = len(stripped) - alpha - digit_space
        if printable and symbolish / max(printable, 1) > 0.45:
            return True
    return False


def clean_text(text: str) -> str:
    value = str(text or "").replace("\u00a0", " ")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def classify_chunk(text: str, seen_hashes: set[str] | None = None, min_chars: int = 80, min_words: int = 12) -> str:
    cleaned = clean_text(text)
    if not cleaned:
        return "EMPTY_CONTENT"
    digest = content_hash(cleaned)
    if seen_hashes is not None:
        if digest in seen_hashes:
            return "DUPLICATE_CONTENT"
        seen_hashes.add(digest)
    if is_page_number(cleaned):
        return "PAGE_NUMBER"
    if is_header_footer(cleaned):
        return "HEADER_FOOTER"
    if is_ocr_noise(cleaned):
        return "OCR_NOISE"
    if is_formula_only(cleaned):
        return "FORMULA_ONLY"
    if is_table_fragment(cleaned):
        return "TABLE_FRAGMENT"
    if len(cleaned) < min_chars or word_count(cleaned) < min_words:
        return "SHORT_FRAGMENT"
    return "EDUCATIONAL_TEXT"


def clean_chunk(chunk: dict[str, Any], seen_hashes: set[str] | None = None, min_chars: int = 80) -> CleanDecision:
    text = clean_text(str(chunk.get("text") or ""))
    category = classify_chunk(text, seen_hashes=seen_hashes, min_chars=min_chars)
    if category == "EDUCATIONAL_TEXT":
        return CleanDecision(True, "kept", text)
    return CleanDecision(False, category, text)


def clean_chunks(chunks: list[dict[str, Any]], min_chars: int = 80) -> tuple[list[dict[str, Any]], dict[str, int]]:
    seen_hashes: set[str] = set()
    cleaned: list[dict[str, Any]] = []
    metrics = {
        "chunks_input": len(chunks),
        "chunks_kept": 0,
        "chunks_removed": 0,
        "duplicates_removed": 0,
        "ocr_removed": 0,
        "short_removed": 0,
        "table_removed": 0,
        "formula_removed": 0,
        "page_number_removed": 0,
        "header_footer_removed": 0,
        "empty_removed": 0,
    }
    reason_to_metric = {
        "DUPLICATE_CONTENT": "duplicates_removed",
        "OCR_NOISE": "ocr_removed",
        "SHORT_FRAGMENT": "short_removed",
        "TABLE_FRAGMENT": "table_removed",
        "FORMULA_ONLY": "formula_removed",
        "PAGE_NUMBER": "page_number_removed",
        "HEADER_FOOTER": "header_footer_removed",
        "EMPTY_CONTENT": "empty_removed",
    }
    for chunk in chunks:
        decision = clean_chunk(chunk, seen_hashes=seen_hashes, min_chars=min_chars)
        if decision.keep:
            item = dict(chunk)
            item["text"] = decision.cleaned_text
            cleaned.append(item)
            metrics["chunks_kept"] += 1
        else:
            metrics["chunks_removed"] += 1
            metric = reason_to_metric.get(decision.reason)
            if metric:
                metrics[metric] += 1
    return cleaned, metrics

