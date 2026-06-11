from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LanguageProfile:
    language: str
    script: str
    confidence: float


class MultilingualSupport:
    """Small multilingual helpers for educational content."""

    def detect_language(self, text: str) -> LanguageProfile:
        if not text:
            return LanguageProfile(language="english", script="latin", confidence=0.0)

        if re.search(r"[\u0C80-\u0CFF]", text):
            return LanguageProfile(language="kannada", script="kannada", confidence=0.98)
        if re.search(r"[\u0900-\u097F]", text):
            return LanguageProfile(language="hindi", script="devanagari", confidence=0.98)
        if re.search(r"[\u0B80-\u0BFF]", text):
            return LanguageProfile(language="tamil", script="tamil", confidence=0.98)
        if re.search(r"[\u0C00-\u0C7F]", text):
            return LanguageProfile(language="telugu", script="telugu", confidence=0.98)
        if re.search(r"[\u0D00-\u0D7F]", text):
            return LanguageProfile(language="malayalam", script="malayalam", confidence=0.98)

        lower = text.lower()
        if any(token in lower for token in [" and ", " the ", " is ", " are "]):
            return LanguageProfile(language="english", script="latin", confidence=0.88)
        return LanguageProfile(language="unknown", script="latin", confidence=0.35)

    def normalize(self, text: str) -> str:
        return " ".join(text.split())

    def prefer_original_language(self, payload: dict[str, Any]) -> dict[str, Any]:
        text = str(payload.get("text", ""))
        profile = self.detect_language(text)
        enriched = dict(payload)
        enriched["language"] = enriched.get("language") or profile.language
        enriched["language_confidence"] = profile.confidence
        return enriched
