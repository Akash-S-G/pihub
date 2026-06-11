from __future__ import annotations

import re


_DASH_PATTERN = re.compile(r"[\u2013\u2014]")
_TRAILING_NUMBER_PATTERN = re.compile(r"\s*-\s*\d+\s*$")
_TRAILING_SEPARATOR_PATTERN = re.compile(r"[\s\-_:\.]+$")
_WHITESPACE_PATTERN = re.compile(r"\s+")


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