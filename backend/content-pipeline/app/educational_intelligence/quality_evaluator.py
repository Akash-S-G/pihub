from __future__ import annotations

from typing import Any


class RetrievalBenchmark:
    def evaluate(self, chunks: list[dict[str, Any]]) -> dict[str, Any]:
        coverage = len([chunk for chunk in chunks if chunk.get("metadata", {}).get("topics")])
        return {
            "chunk_count": len(chunks),
            "topic_coverage": coverage,
            "coverage_ratio": round(coverage / max(1, len(chunks)), 2),
        }


class QuizValidator:
    def validate(self, quizzes: list[dict[str, Any]]) -> dict[str, Any]:
        valid = 0
        for quiz in quizzes:
            if quiz.get("question") and quiz.get("answer") is not None:
                valid += 1
        return {
            "total": len(quizzes),
            "valid": valid,
            "invalid": len(quizzes) - valid,
            "valid_ratio": round(valid / max(1, len(quizzes)), 2),
        }


class GlossaryValidator:
    def validate(self, glossary: list[dict[str, Any]]) -> dict[str, Any]:
        valid = [entry for entry in glossary if entry.get("term") and entry.get("definition")]
        return {
            "total": len(glossary),
            "valid": len(valid),
            "valid_ratio": round(len(valid) / max(1, len(glossary)), 2),
        }


class EducationalQualityScore:
    def score(
        self,
        retrieval: dict[str, Any],
        quizzes: dict[str, Any],
        glossary: dict[str, Any],
    ) -> float:
        return round(
            0.4 * retrieval.get("coverage_ratio", 0.0)
            + 0.3 * quizzes.get("valid_ratio", 0.0)
            + 0.3 * glossary.get("valid_ratio", 0.0),
            3,
        )


class QualityEvaluator:
    def __init__(self) -> None:
        self.retrieval_benchmark = RetrievalBenchmark()
        self.quiz_validator = QuizValidator()
        self.glossary_validator = GlossaryValidator()
        self.scorer = EducationalQualityScore()

    def evaluate(self, chunks: list[dict[str, Any]], quizzes: list[dict[str, Any]], glossary: list[dict[str, Any]]) -> dict[str, Any]:
        retrieval = self.retrieval_benchmark.evaluate(chunks)
        quiz = self.quiz_validator.validate(quizzes)
        glossary_report = self.glossary_validator.validate(glossary)
        return {
            "retrieval": retrieval,
            "quiz": quiz,
            "glossary": glossary_report,
            "quality_score": self.scorer.score(retrieval, quiz, glossary_report),
        }
