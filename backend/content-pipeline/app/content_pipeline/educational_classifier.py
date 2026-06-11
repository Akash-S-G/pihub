from __future__ import annotations

import re


class EducationalClassifier:
    """Classify chunk type for educational ranking and retrieval."""

    PATTERNS: list[tuple[str, re.Pattern[str]]] = [
        ("definition", re.compile(r"\b(definition|defined as|what is)\b", re.IGNORECASE)),
        ("formula", re.compile(r"(=|\+|\-|\*|/|\^|\bformula\b|\bequation\b)", re.IGNORECASE)),
        ("example", re.compile(r"\b(example|for example|e\.g\.)\b", re.IGNORECASE)),
        ("experiment", re.compile(r"\b(experiment|activity|procedure|observation)\b", re.IGNORECASE)),
        ("qa", re.compile(r"\b(question|answer|q\.|a\.)\b", re.IGNORECASE)),
    ]

    def classify(self, text: str) -> str:
        for label, pattern in self.PATTERNS:
            if pattern.search(text):
                return label
        return "explanation"
