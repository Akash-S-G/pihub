from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BenchmarkQuestion:
    query: str
    expected_topic: str
    expected_chapter: str | None = None
    expected_language: str | None = None
    benchmark_type: str = "exact_topic"


DEFAULT_BENCHMARK_QUESTIONS: list[BenchmarkQuestion] = [
    BenchmarkQuestion(query="photosynthesis", expected_topic="photosynthesis", expected_chapter="Nutrition in Plants"),
    BenchmarkQuestion(query="prerequisite for nutrition", expected_topic="nutrition", expected_chapter="Nutrition in Plants", benchmark_type="prerequisite"),
    BenchmarkQuestion(query="chapter aware plant nutrition", expected_topic="nutrition", expected_chapter="Nutrition in Plants", benchmark_type="chapter_aware"),
    BenchmarkQuestion(query="শ্বসন", expected_topic="respiration", expected_language="kannada", benchmark_type="multilingual"),
    BenchmarkQuestion(query="glucose definition", expected_topic="glucose", benchmark_type="glossary"),
]
