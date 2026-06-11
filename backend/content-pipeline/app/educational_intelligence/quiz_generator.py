from __future__ import annotations

from typing import Any

from app.educational_intelligence.glossary_extractor import GlossaryExtractor


class QuizGenerator:
    """Generate lightweight educational quizzes from chunks and glossary entries."""

    def __init__(self) -> None:
        self.glossary_extractor = GlossaryExtractor()

    def generate(self, chunks: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
        glossary = self.glossary_extractor.extract(chunks)
        quizzes: list[dict[str, Any]] = []

        for entry in glossary[:limit]:
            term = entry["term"]
            definition = entry["definition"]
            distractors = self._build_distractors(term, glossary)
            quizzes.append({
                "question_type": "mcq",
                "question": f"What best describes {term}?",
                "options": [term, *distractors[:3]],
                "answer": term,
                "chapter": entry.get("chapter"),
                "subject": entry.get("subject"),
            })
            quizzes.append({
                "question_type": "true_false",
                "question": f"{definition}",
                "answer": True,
                "chapter": entry.get("chapter"),
                "subject": entry.get("subject"),
            })
            quizzes.append({
                "question_type": "fill_blank",
                "question": definition.replace(term, "______"),
                "answer": term,
                "chapter": entry.get("chapter"),
                "subject": entry.get("subject"),
            })

        return quizzes[: max(limit * 3, 3)]

    def _build_distractors(self, term: str, glossary: list[dict[str, Any]]) -> list[str]:
        distractors = []
        term_l = term.lower()
        for entry in glossary:
            candidate = entry["term"]
            if candidate.lower() != term_l and candidate not in distractors:
                distractors.append(candidate)
        if not distractors:
            distractors = ["Water", "Energy", "Process", "Structure"]
        return distractors
