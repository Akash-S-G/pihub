from __future__ import annotations

import re
from typing import Any


class DefinitionExtractor:
    def extract_definitions(self, text: str) -> list[dict[str, str]]:
        matches: list[dict[str, str]] = []
        for line in [segment.strip() for segment in text.splitlines() if segment.strip()]:
            patterns = [
                r"^(?P<term>[A-Za-z][A-Za-z0-9\- ]{2,40})\s*[:\-]\s*(?P<definition>.{10,220})$",
                r"^(?P<term>[A-Za-z][A-Za-z0-9\- ]{2,40})\s+is\s+(?P<definition>.{10,220})$",
            ]
            for pattern in patterns:
                match = re.match(pattern, line, re.IGNORECASE)
                if match:
                    matches.append({"term": match.group("term").strip(), "definition": match.group("definition").strip().rstrip(".")})
                    break
        return matches


class FormulaExtractor:
    def extract_formulas(self, text: str) -> list[dict[str, str]]:
        formulas: list[dict[str, str]] = []
        for line in [segment.strip() for segment in text.splitlines() if segment.strip()]:
            if re.search(r"[=+\-*/^]", line) and len(line) < 180:
                formulas.append({"formula": line, "definition": "Formula referenced in chapter text"})
        return formulas


class GlossaryExtractor:
    """Extract glossary terms from educational chunks."""

    def __init__(self) -> None:
        self.definition_extractor = DefinitionExtractor()
        self.formula_extractor = FormulaExtractor()

    def extract(self, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        terms: dict[str, dict[str, Any]] = {}
        for chunk in chunks:
            text = str(chunk.get("text", ""))
            metadata = chunk.get("metadata", {})
            for item in self.definition_extractor.extract_definitions(text):
                term = item["term"]
                terms[term.lower()] = {
                    "term": term,
                    "definition": item["definition"],
                    "chapter": metadata.get("chapter"),
                    "subject": metadata.get("subject"),
                    "source": "definition",
                }
            for item in self.formula_extractor.extract_formulas(text):
                term = item["formula"]
                terms[term.lower()] = {
                    "term": term,
                    "definition": item["definition"],
                    "chapter": metadata.get("chapter"),
                    "subject": metadata.get("subject"),
                    "source": "formula",
                }

            for topic in metadata.get("topics", []):
                key = str(topic).lower()
                if key not in terms:
                    terms[key] = {
                        "term": str(topic),
                        "definition": self._term_hint(topic, text),
                        "chapter": metadata.get("chapter"),
                        "subject": metadata.get("subject"),
                        "source": "topic_hint",
                    }

        return list(terms.values())

    def _term_hint(self, term: str, text: str) -> str:
        sentences = [segment.strip() for segment in re.split(r"(?<=[.!?।])\s+", text) if segment.strip()]
        for sentence in sentences:
            if str(term).lower() in sentence.lower():
                return sentence[:220]
        return f"Key concept related to {term}"
