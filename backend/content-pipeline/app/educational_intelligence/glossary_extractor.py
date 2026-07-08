from __future__ import annotations

import re
from typing import Any

from app.educational_intelligence.artifact_cleaning import (
    clean_text,
    dedupe_by_key,
    is_meaningful_term,
    is_noisy_text,
    pick_anchor_sentence,
)


class DefinitionExtractor:
    def extract_definitions(self, text: str) -> list[dict[str, str]]:
        matches: list[dict[str, str]] = []
        for line in [segment.strip() for segment in text.splitlines() if segment.strip()]:
            line = clean_text(line)
            patterns = [
                r"^(?P<term>[\w\u0900-\u097F\u0C80-\u0CFF][\w\u0900-\u097F\u0C80-\u0CFF\- ]{1,60})\s*[:\-]\s*(?P<definition>.{10,220})$",
                r"^(?P<term>[\w\u0900-\u097F\u0C80-\u0CFF][\w\u0900-\u097F\u0C80-\u0CFF\- ]{1,60})\s+is\s+(?P<definition>.{10,220})$",
                r"^(?P<term>[\w\u0900-\u097F\u0C80-\u0CFF][\w\u0900-\u097F\u0C80-\u0CFF\- ]{1,60})\s+(?:means|refers to|describes|explains|shows)\s+(?P<definition>.{10,220})$",
            ]
            for pattern in patterns:
                match = re.match(pattern, line, re.IGNORECASE)
                if match:
                    term = clean_text(match.group("term"))
                    definition = clean_text(match.group("definition")).rstrip(".")
                    if term and definition and is_meaningful_term(term) and not is_noisy_text(definition):
                        matches.append({"term": term, "definition": definition})
                    break
        return matches


class FormulaExtractor:
    def extract_formulas(self, text: str) -> list[dict[str, str]]:
        formulas: list[dict[str, str]] = []
        for line in [segment.strip() for segment in text.splitlines() if segment.strip()]:
            line = clean_text(line)
            if re.search(r"[=+\-*/^]", line) and len(line) < 180 and not is_noisy_text(line):
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
            text = clean_text(str(chunk.get("text", "")))
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
                    "language": metadata.get("language"),
                    "source": "formula",
                }

            for topic in metadata.get("topics", []):
                key = clean_text(str(topic)).lower()
                if key and key not in terms and is_meaningful_term(key):
                    terms[key] = {
                        "term": clean_text(str(topic)),
                        "definition": self._term_hint(topic, text),
                        "chapter": metadata.get("chapter"),
                        "subject": metadata.get("subject"),
                        "language": metadata.get("language"),
                        "source": "topic_hint",
                    }

        filtered = [
            entry for entry in terms.values()
            if is_meaningful_term(entry.get("term", "")) and not is_noisy_text(entry.get("definition", ""))
        ]
        return dedupe_by_key(filtered, "term")

    def _term_hint(self, term: str, text: str) -> str:
        sentences = [segment.strip() for segment in re.split(r"(?<=[.!?।])\s+", text) if segment.strip()]
        for sentence in sentences:
            if str(term).lower() in sentence.lower():
                return pick_anchor_sentence(sentence, term)
        if re.search(r"[\u0C80-\u0CFF]", f"{term} {text}"):
            return f"{clean_text(str(term))} ಗೆ ಸಂಬಂಧಿಸಿದ ಪ್ರಮುಖ ಪರಿಕಲ್ಪನೆ"
        return f"Key concept related to {clean_text(str(term))}"
