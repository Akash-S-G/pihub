from __future__ import annotations

from typing import Any

from app.educational_intelligence.artifact_cleaning import clean_text, is_meaningful_term
from app.educational_intelligence.glossary_extractor import GlossaryExtractor


class FlashcardGenerator:
    """Create revision flashcards from glossary and chapter content."""

    def __init__(self) -> None:
        self.glossary_extractor = GlossaryExtractor()

    def generate(self, chunks: list[dict[str, Any]], limit: int = 12) -> list[dict[str, Any]]:
        cards: list[dict[str, Any]] = []
        for entry in self.glossary_extractor.extract(chunks):
            term = clean_text(str(entry.get("term") or ""))
            definition = clean_text(str(entry.get("definition") or ""))
            if not term or not definition or not is_meaningful_term(term):
                continue
            cards.append({
                "front": f"What does the chapter say about {term}?",
                "back": definition,
                "chapter": entry.get("chapter"),
                "subject": entry.get("subject"),
            })
            if len(cards) >= limit:
                break
        return cards
