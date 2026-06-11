from __future__ import annotations

from typing import Any

from ..api.pack_response_models import BenchmarkResult
from .benchmark_questions import BenchmarkQuestion, DEFAULT_BENCHMARK_QUESTIONS


class RetrievalBenchmark:
    def __init__(self, questions: list[BenchmarkQuestion] | None = None) -> None:
        self.questions = questions or DEFAULT_BENCHMARK_QUESTIONS

    def run(self, packs: list[dict[str, Any]]) -> BenchmarkResult:
        report: list[dict[str, Any]] = []
        exact_matches = 0
        total_score = 0.0
        for question in self.questions:
            candidate, score = self._best_match(question, packs)
            report.append({
                "query": question.query,
                "expected_topic": question.expected_topic,
                "matched_pack_id": candidate.get("pack_id") if candidate else None,
                "matched_topic": candidate.get("subject") if candidate else None,
                "score": round(score, 4),
            })
            total_score += score
            if candidate and self._matches_question(candidate, question):
                exact_matches += 1
        average_score = total_score / max(1, len(self.questions))
        return BenchmarkResult(
            benchmark_name="educational_retrieval",
            total_questions=len(self.questions),
            exact_matches=exact_matches,
            average_score=round(average_score, 4),
            report=report,
        )

    def _best_match(self, question: BenchmarkQuestion, packs: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, float]:
        best_pack: dict[str, Any] | None = None
        best_score = -1.0
        for pack in packs:
            score = self._score_pack(pack, question)
            if score > best_score:
                best_score = score
                best_pack = pack
        return best_pack, max(0.0, best_score)

    def _score_pack(self, pack: dict[str, Any], question: BenchmarkQuestion) -> float:
        pack_text = " ".join(str(pack.get(key, "")) for key in ("pack_id", "subject", "chapter", "language")).lower()
        query_tokens = [token for token in question.query.lower().split() if token]
        overlap = sum(1 for token in query_tokens if token in pack_text)
        score = overlap / max(1, len(query_tokens))
        if question.expected_chapter and question.expected_chapter.lower() in pack_text:
            score += 0.35
        if question.expected_language and question.expected_language.lower() in pack_text:
            score += 0.2
        if question.expected_topic and question.expected_topic.lower() in pack_text:
            score += 0.4
        return min(score, 1.0)

    @staticmethod
    def _matches_question(pack: dict[str, Any], question: BenchmarkQuestion) -> bool:
        pack_text = " ".join(str(pack.get(key, "")) for key in ("pack_id", "subject", "chapter", "language")).lower()
        expected = [question.expected_topic, question.expected_chapter, question.expected_language]
        return all(not value or value.lower() in pack_text for value in expected)
