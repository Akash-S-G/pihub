from __future__ import annotations

import re


_DASH_PATTERN = re.compile(r"[\u2013\u2014]")
_TRAILING_NUMBER_PATTERN = re.compile(r"\s*-\s*\d+\s*$")
_TRAILING_SEPARATOR_PATTERN = re.compile(r"[\s\-_:\.]+$")
_WHITESPACE_PATTERN = re.compile(r"\s+")

LANGUAGE_ALIASES = {
    "en": "en",
    "eng": "en",
    "english": "en",
    "en-us": "en",
    "en-gb": "en",
    "hi": "hi",
    "hin": "hi",
    "hindi": "hi",
    "hi-in": "hi",
    "kn": "kn",
    "kan": "kn",
    "kannada": "kn",
    "kannada-medium": "kn",
    "kannada medium": "kn",
    "kn-in": "kn",
}

LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "kn": "Kannada",
}

LANGUAGE_FILTER_ALIASES = {
    "en": ["en", "eng", "english"],
    "hi": ["hi", "hin", "hindi"],
    "kn": ["kn", "kan", "kannada"],
}


def normalize_curriculum_name(text: str | None) -> str:
    if text is None:
        return ""

    value = str(text).strip().lower()
    if not value:
        return ""

    value = value.replace(".pdf", "")
    value = _DASH_PATTERN.sub("-", value)
    value = _TRAILING_NUMBER_PATTERN.sub("", value)
    value = _TRAILING_SEPARATOR_PATTERN.sub("", value)
    value = _WHITESPACE_PATTERN.sub(" ", value)
    return value.strip()


def normalize_language_code(language: str | None) -> str:
    if language is None:
        return ""

    value = str(language).strip().lower().replace("_", "-")
    if not value:
        return ""

    if value in LANGUAGE_ALIASES:
        return LANGUAGE_ALIASES[value]

    if value.startswith("en"):
        return "en"
    if value.startswith("hi"):
        return "hi"
    if value.startswith("kn") or value.startswith("kan"):
        return "kn"

    return normalize_curriculum_name(value)


def language_display_name(language: str | None) -> str:
    code = normalize_language_code(language)
    if not code:
        return "Unknown"
    return LANGUAGE_NAMES.get(code, code.title())


def language_filter_values(language: str | None) -> list[str]:
    code = normalize_language_code(language)
    if not code:
        return []
    values = [code, *LANGUAGE_FILTER_ALIASES.get(code, [])]
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        normalized = normalize_curriculum_name(value) if value not in {code} else value
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(normalized)
    return unique
