from __future__ import annotations

import re
from collections import Counter
from typing import Any


WORD_RE = re.compile(r"[A-Za-z0-9]+")
GENERIC_TERMS = {
    "chapter",
    "grade",
    "figure",
    "image",
    "images",
    "activity",
    "exercise",
    "question",
    "questions",
    "example",
    "examples",
    "page",
    "textbook",
    "part",
    "science",
    "maths",
    "mathematics",
    "social",
    "class",
}


def normalize_text(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def word_count(text: Any) -> int:
    return len(WORD_RE.findall(str(text or "")))


def token_set(text: Any) -> set[str]:
    return {
        token.lower()
        for token in WORD_RE.findall(str(text or ""))
        if len(token) >= 4 and token.lower() not in GENERIC_TERMS
    }


def key_terms(text: Any, limit: int = 30) -> list[str]:
    counts = Counter(token for token in token_set(text))
    return [term for term, _ in counts.most_common(limit)]


def ratio(value: float, total: float) -> float:
    return round(float(value) / max(float(total), 1.0), 4)


def percent(value: float, total: float) -> float:
    return round(100.0 * ratio(value, total), 2)


def has_boilerplate(text: Any) -> bool:
    lowered = normalize_text(text)
    return bool(
        re.search(
            r"\b(isbn|copyright|all rights reserved|published by|printed at|reprint|ncert|"
            r"contents|table of contents|answer key)\b",
            lowered,
        )
    )


def has_page_artifact(text: Any) -> bool:
    raw = str(text or "")
    if "\x08" in raw or "\x07" in raw or "\ufffd" in raw:
        return True
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    if not lines:
        return True
    short_page_lines = sum(1 for line in lines if re.fullmatch(r"\d{1,4}", line))
    figure_lines = sum(1 for line in lines if re.match(r"^(fig|table)\.?\s*\d+", line, re.I))
    return (short_page_lines + figure_lines) / max(1, len(lines)) > 0.2


def readable_educational_text(text: Any) -> bool:
    value = str(text or "")
    words = word_count(value)
    if words < 60:
        return False
    if has_boilerplate(value) or has_page_artifact(value):
        return False
    alpha = sum(1 for char in value if char.isalpha())
    return alpha / max(1, len(value)) > 0.45
