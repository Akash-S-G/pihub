from __future__ import annotations

import re
from typing import Any

from app.educational_intelligence.artifact_cleaning import build_mcq_options, clean_text, is_meaningful_term
from app.educational_intelligence.glossary_extractor import GlossaryExtractor
from shared.text_normalization import normalize_language_code


class QuizGenerator:
    """Generate lightweight educational quizzes from chunks and glossary entries."""

    def __init__(self) -> None:
        self.glossary_extractor = GlossaryExtractor()

    def generate(self, chunks: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
        glossary = self.glossary_extractor.extract(chunks)
        quizzes: list[dict[str, Any]] = []
        language = self._infer_language(chunks, glossary)
        definitions = [
            clean_text(str(entry.get("definition") or ""))
            for entry in glossary
            if clean_text(str(entry.get("definition") or ""))
        ]

        for entry in glossary:
            term = clean_text(str(entry.get("term") or ""))
            definition = clean_text(str(entry.get("definition") or ""))
            if not term or not definition or not is_meaningful_term(term):
                continue
            distractors = self._build_distractors(definition, definitions, language)
            options = build_mcq_options(definition, distractors, limit=4, language=language)
            quizzes.append({
                "question_type": "mcq",
                "question": self._question_template(term, language),
                "options": options,
                "answer": definition,
                "chapter": entry.get("chapter"),
                "subject": entry.get("subject"),
                "language": entry.get("language") or language,
            })
            quizzes.append({
                "question_type": "true_false",
                "question": definition,
                "answer": True,
                "chapter": entry.get("chapter"),
                "subject": entry.get("subject"),
                "language": entry.get("language") or language,
            })
            quizzes.append({
                "question_type": "fill_blank",
                "question": re.sub(re.escape(term), "______", definition, flags=re.IGNORECASE),
                "answer": term,
                "chapter": entry.get("chapter"),
                "subject": entry.get("subject"),
                "language": entry.get("language") or language,
            })
            if len(quizzes) >= max(limit * 3, 3):
                break

        return quizzes[: max(limit * 3, 3)]

    def _build_distractors(self, answer: str, glossary_definitions: list[str], language: str) -> list[str]:
        distractors = []
        answer_l = answer.lower()
        for candidate in glossary_definitions:
            if candidate.lower() != answer_l and candidate not in distractors:
                distractors.append(candidate)
        if not distractors:
            distractors = self._localized_distractors(answer, language)
        return distractors

    @staticmethod
    def _infer_language(chunks: list[dict[str, Any]], glossary: list[dict[str, Any]]) -> str:
        for item in glossary:
            language = normalize_language_code(item.get("language"))
            if language:
                return language
        for chunk in chunks:
            language = normalize_language_code(chunk.get("metadata", {}).get("language"))
            if language:
                return language
        return "en"

    @staticmethod
    def _localized_distractors(answer: str, language: str) -> list[str]:
        if language == "kn" or re.search(r"[\u0C80-\u0CFF]", answer):
            return [
                "ಮತ್ತೊಂದು ಅಧ್ಯಾಯದಿಂದ ಸಂಬಂಧಿಸದ ಕಲ್ಪನೆ",
                "ಸಾಮಾನ್ಯ ಪಠ್ಯಪುಸ್ತಕ ಪದಬಳಕೆ",
                "ಸಂಪೂರ್ಣವಾಗಿ ಬೇರೆ ಕಲ್ಪನೆ",
                "ಹೊಂದಿಕೆಯಾಗದ ಹೇಳಿಕೆ",
            ]
        if language == "hi" or re.search(r"[\u0900-\u097F]", answer):
            return [
                "दूसरे अध्याय का असंबंधित विचार",
                "सामान्य पाठ्यपुस्तक वाक्यांश",
                "पूरी तरह अलग अवधारणा",
                "मिलान न करने वाला कथन",
            ]
        return [
            "An unrelated idea from another chapter",
            "A generic textbook phrase",
            "A different concept entirely",
            "A non-matching statement",
        ]

    @staticmethod
    def _question_template(term: str, language: str) -> str:
        if language == "kn":
            return f"{term} ಅನ್ನು ಅತ್ಯುತ್ತಮವಾಗಿ ವಿವರಿಸುವುದು ಯಾವುದು?"
        if language == "hi":
            return f"{term} का सबसे अच्छा वर्णन कौन सा है?"
        return f"What best describes {term}?"
