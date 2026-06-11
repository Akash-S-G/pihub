from __future__ import annotations

import re


class ConceptBoundaryDetector:
    """Detect boundaries around definition/example/experiment/QA blocks."""

    DEFINITION_PATTERNS = [
        re.compile(r"^definition\s*[:\-]", re.IGNORECASE),
        re.compile(r"^what is\s+", re.IGNORECASE),
        re.compile(r"\bdefined as\b", re.IGNORECASE),
    ]
    EXAMPLE_PATTERNS = [
        re.compile(r"^example\s*[:\-]", re.IGNORECASE),
        re.compile(r"^for example\b", re.IGNORECASE),
    ]
    EXPERIMENT_PATTERNS = [
        re.compile(r"^experiment\s*[:\-]", re.IGNORECASE),
        re.compile(r"^activity\s*[:\-]", re.IGNORECASE),
        re.compile(r"^procedure\s*[:\-]", re.IGNORECASE),
    ]
    QA_PATTERNS = [
        re.compile(r"^(q\.|question)\s*[:\-]", re.IGNORECASE),
        re.compile(r"^(a\.|answer)\s*[:\-]", re.IGNORECASE),
    ]

    def is_boundary_start(self, paragraph: str) -> bool:
        text = paragraph.strip()
        if not text:
            return False
        return any(
            pattern.search(text)
            for pattern in [
                *self.DEFINITION_PATTERNS,
                *self.EXAMPLE_PATTERNS,
                *self.EXPERIMENT_PATTERNS,
                *self.QA_PATTERNS,
            ]
        )

    def boundary_label(self, paragraph: str) -> str | None:
        text = paragraph.strip()
        if any(p.search(text) for p in self.DEFINITION_PATTERNS):
            return "definition"
        if any(p.search(text) for p in self.EXPERIMENT_PATTERNS):
            return "experiment"
        if any(p.search(text) for p in self.EXAMPLE_PATTERNS):
            return "example"
        if any(p.search(text) for p in self.QA_PATTERNS):
            return "qa"
        return None
