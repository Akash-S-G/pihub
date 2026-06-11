from __future__ import annotations

from .benchmark_questions import DEFAULT_BENCHMARK_QUESTIONS


class CurriculumTestSuite:
    def build(self) -> list[dict[str, str | None]]:
        return [
            {
                "query": question.query,
                "expected_topic": question.expected_topic,
                "expected_chapter": question.expected_chapter,
                "expected_language": question.expected_language,
                "benchmark_type": question.benchmark_type,
            }
            for question in DEFAULT_BENCHMARK_QUESTIONS
        ]
