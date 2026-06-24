from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field


_STOPWORDS = {
    "about",
    "after",
    "also",
    "because",
    "before",
    "between",
    "chapter",
    "concept",
    "could",
    "does",
    "from",
    "have",
    "into",
    "like",
    "more",
    "should",
    "that",
    "their",
    "there",
    "this",
    "what",
    "when",
    "where",
    "which",
    "with",
    "would",
}


class AnswerEvaluation(BaseModel):
    context_used: bool
    context_overlap_score: float
    hallucination_risk: str
    language_correct: bool
    grade_appropriate: bool
    completeness_score: float
    issues: list[str] = Field(default_factory=list)


def evaluate_answer(
    *,
    question: str,
    answer: str,
    context: list[Any] | None = None,
    language: str | None = None,
    grade: int | None = None,
) -> AnswerEvaluation:
    context_text = " ".join(_context_text(item) for item in context or [])
    overlap = _overlap_score(answer, context_text)
    issues: list[str] = []

    if context and overlap < 0.05:
        issues.append("low_context_overlap")
    if not answer.strip():
        issues.append("empty_answer")
    if _looks_like_refusal(answer):
        issues.append("generic_or_refusal_answer")

    language_correct = _language_matches(answer, language)
    if not language_correct:
        issues.append("language_mismatch")

    grade_appropriate = _grade_appropriate(answer, grade)
    if not grade_appropriate:
        issues.append("grade_appropriateness_risk")

    completeness = _completeness_score(question, answer)
    if completeness < 0.45:
        issues.append("low_completeness")

    hallucination_risk = "low"
    if context and overlap < 0.03 and len(answer.split()) > 40:
        hallucination_risk = "high"
    elif context and overlap < 0.08:
        hallucination_risk = "medium"

    return AnswerEvaluation(
        context_used=bool(context and overlap >= 0.05),
        context_overlap_score=round(overlap, 3),
        hallucination_risk=hallucination_risk,
        language_correct=language_correct,
        grade_appropriate=grade_appropriate,
        completeness_score=round(completeness, 3),
        issues=issues,
    )


def _context_text(item: Any) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        for key in ("content", "text", "chunk", "summary", "definition"):
            value = item.get(key)
            if value:
                return str(value)
        return " ".join(str(value) for value in item.values() if isinstance(value, (str, int, float)))
    if hasattr(item, "model_dump"):
        return _context_text(item.model_dump())
    return str(item)


def _terms(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[A-Za-z][A-Za-z0-9_-]{3,}", text.lower())
        if token not in _STOPWORDS
    }


def _overlap_score(answer: str, context_text: str) -> float:
    answer_terms = _terms(answer)
    context_terms = _terms(context_text)
    if not answer_terms or not context_terms:
        return 0.0
    return len(answer_terms & context_terms) / max(1, len(answer_terms))


def _language_matches(answer: str, language: str | None) -> bool:
    code = (language or "en").lower()
    if code.startswith("kn"):
        return bool(re.search(r"[\u0C80-\u0CFF]", answer))
    if code.startswith("hi"):
        return bool(re.search(r"[\u0900-\u097F]", answer))
    return True


def _grade_appropriate(answer: str, grade: int | None) -> bool:
    if grade is None:
        return True
    words = answer.split()
    if grade <= 5:
        return len(words) <= 180
    if grade <= 8:
        return len(words) <= 260
    return len(words) <= 360


def _completeness_score(question: str, answer: str) -> float:
    words = answer.split()
    if not words:
        return 0.0
    score = min(1.0, len(words) / 80)
    if any(marker in answer.lower() for marker in ("for example", "because", "therefore", "means", "is called")):
        score += 0.15
    if question.strip().endswith("?") and len(words) >= 25:
        score += 0.1
    return min(1.0, score)


def _looks_like_refusal(answer: str) -> bool:
    lowered = answer.lower()
    return any(
        phrase in lowered
        for phrase in (
            "i don't have enough information",
            "i cannot answer",
            "no relevant context",
            "as an ai language model",
        )
    )
