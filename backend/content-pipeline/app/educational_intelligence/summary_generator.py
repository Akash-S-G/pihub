from __future__ import annotations

import re
from typing import Any

from app.educational_intelligence.artifact_cleaning import clean_text, is_noisy_text, pick_anchor_sentence, sentence_split
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
            text = clean_text(str(chunk.get("text", ""))).strip()
            if not text:
                continue
            if chunk.get("metadata", {}).get("chunk_type") in {"definition", "formula", "example", "experiment", "qa", "summary"}:
                parts.append(text)
            elif len(parts) < 6:
                parts.append(text)
        return "\n".join(parts)

    def generate(self, chunks: list[dict[str, Any]], chapter: str | None = None, topic: str | None = None) -> dict[str, Any]:
        text = self._collect_focus_text(chunks)
        sentences = [sentence for sentence in self._sentences(text) if sentence and not is_noisy_text(sentence)]
        summary_sentences = [pick_anchor_sentence(sentence) for sentence in sentences[:4]] if sentences else []
        summary_sentences = [sentence for sentence in summary_sentences if sentence]
        summary = " ".join(summary_sentences).strip()
        if not summary and chunks:
            summary = clean_text(str(chunks[0].get("text", "")))[:240]

        focus_terms: list[str] = []
        for chunk in chunks:
            for term in (chunk.get("metadata", {}).get("topics") or []):
                term_clean = clean_text(str(term))
                if term_clean and term_clean not in focus_terms and not is_noisy_text(term_clean):
                    focus_terms.append(term_clean)
            for term in (chunk.get("metadata", {}).get("concepts") or []):
                term_clean = clean_text(str(term))
                if term_clean and term_clean not in focus_terms and not is_noisy_text(term_clean):
                    focus_terms.append(term_clean)

        revision_notes = [f"Remember: {sentence}" for sentence in summary_sentences[:3]]
        profile = self.multilingual.detect_language(text)
        if profile.language == "kn":
            revision_notes = [note.replace("Remember: ", "ನೆನಪಿಡಿ: ") for note in revision_notes]
        elif profile.language == "hi":
            revision_notes = [note.replace("Remember: ", "याद रखें: ") for note in revision_notes]

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
        title = "Quick Review"
        if generated["language"] == "kn":
            title = "ತ್ವರಿತ ವಿಮರ್ಶೆ"
        elif generated["language"] == "hi":
            title = "त्वरित समीक्षा"
        return {
            "title": generated["chapter"] or title,
            "summary": generated["summary"],
            "bullets": [note.replace("Remember: ", "") for note in generated["revision_notes"]],
        }
