from __future__ import annotations

from typing import Any

from app.educational_intelligence.glossary_extractor import GlossaryExtractor


class FlashcardGenerator:
    """Create revision flashcards from glossary and chapter content."""

    def __init__(self) -> None:
        self.glossary_extractor = GlossaryExtractor()

    def generate(self, chunks: list[dict[str, Any]], limit: int = 12) -> list[dict[str, Any]]:
        cards: list[dict[str, Any]] = []
        for entry in self.glossary_extractor.extract(chunks)[:limit]:
            cards.append({
                "front": f"What is {entry['term']}?",
                "back": entry["definition"],
                "chapter": entry.get("chapter"),
                "subject": entry.get("subject"),
            })
        return cards
