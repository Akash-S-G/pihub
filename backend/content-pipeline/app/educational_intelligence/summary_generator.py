from __future__ import annotations

import re
from typing import Any

from app.educational_intelligence.multilingual_support import MultilingualSupport


class SummaryGenerator:
    """Generate chapter/topic summaries and revision notes from chunks."""

    def __init__(self) -> None:
        self.multilingual = MultilingualSupport()

    def _sentences(self, text: str) -> list[str]:
        sentences = [segment.strip() for segment in re.split(r"(?<=[.!?।])\s+", text.strip()) if segment.strip()]
        return sentences

    def _collect_focus_text(self, chunks: list[dict[str, Any]]) -> str:
        parts: list[str] = []
        for chunk in chunks:
            text = str(chunk.get("text", "")).strip()
            if not text:
                continue
            if chunk.get("metadata", {}).get("chunk_type") in {"definition", "formula", "example", "experiment", "qa"}:
                parts.append(text)
            elif len(parts) < 6:
                parts.append(text)
        return "\n".join(parts)

    def generate(self, chunks: list[dict[str, Any]], chapter: str | None = None, topic: str | None = None) -> dict[str, Any]:
        text = self._collect_focus_text(chunks)
        sentences = self._sentences(text)
        summary_sentences = sentences[:4] if len(sentences) >= 4 else sentences
        summary = " ".join(summary_sentences).strip()
        if not summary and chunks:
            summary = str(chunks[0].get("text", ""))[:240]

        focus_terms: list[str] = []
        for chunk in chunks:
            for term in (chunk.get("metadata", {}).get("topics") or []):
                if term not in focus_terms:
                    focus_terms.append(term)
            for term in (chunk.get("metadata", {}).get("concepts") or []):
                if term not in focus_terms:
                    focus_terms.append(term)

        revision_notes = [f"Remember: {sentence}" for sentence in summary_sentences[:3]]
        profile = self.multilingual.detect_language(text)

        return {
            "chapter": chapter or (chunks[0].get("metadata", {}).get("chapter") if chunks else None),
            "topic": topic or (focus_terms[0] if focus_terms else None),
            "language": profile.language,
            "summary": summary,
            "key_points": focus_terms[:8],
            "revision_notes": revision_notes,
            "chunk_count": len(chunks),
        }

    def quick_review(self, chunks: list[dict[str, Any]]) -> dict[str, Any]:
        generated = self.generate(chunks)
        return {
            "title": generated["chapter"] or "Quick Review",
            "summary": generated["summary"],
            "bullets": [note.replace("Remember: ", "") for note in generated["revision_notes"]],
        }
