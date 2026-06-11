from __future__ import annotations

from typing import Any

from ..api.pack_response_models import QualityScoreResponse


class QualityScorer:
    def score(self, manifest: dict[str, Any], artifacts: dict[str, Any], validation_report: dict[str, Any] | None = None) -> QualityScoreResponse:
        artifact_counts = manifest.get("artifact_counts", {})
        glossary_count = len(artifacts.get("glossary", []))
        quiz_count = len(artifacts.get("quizzes", []))
        flashcard_count = len(artifacts.get("flashcards", []))
        summary_count = len(artifacts.get("summaries", []))
        content_count = len(artifacts.get("content", []))

        retrieval_score = min(1.0, float(artifact_counts.get("retrieval_index", 0)) / max(1, content_count))
        coverage_score = min(1.0, float(content_count + glossary_count + quiz_count + flashcard_count + summary_count) / max(1, content_count * 5))
        quiz_quality = min(1.0, float(quiz_count) / max(1, content_count))
        glossary_quality = min(1.0, float(glossary_count) / max(1, content_count))
        flashcard_quality = min(1.0, float(flashcard_count) / max(1, content_count))
        overall_score = round((retrieval_score + coverage_score + quiz_quality + glossary_quality + flashcard_quality) / 5.0, 4)

        return QualityScoreResponse(
            retrieval_score=round(retrieval_score, 4),
            coverage_score=round(coverage_score, 4),
            quiz_quality=round(quiz_quality, 4),
            glossary_quality=round(glossary_quality, 4),
            flashcard_quality=round(flashcard_quality, 4),
            overall_score=overall_score,
        )
