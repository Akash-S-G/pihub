from __future__ import annotations

from typing import Any

from ..api.pack_response_models import BenchmarkResult, QualityScoreResponse
from .quality_scoring import QualityScorer
from .retrieval_benchmark import RetrievalBenchmark


class EducationalEvalRunner:
    def __init__(self) -> None:
        self.scorer = QualityScorer()
        self.benchmark = RetrievalBenchmark()

    def run(self, manifest: dict[str, Any], artifacts: dict[str, Any], pack_list: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        scores: QualityScoreResponse = self.scorer.score(manifest, artifacts)
        benchmark: BenchmarkResult | None = self.benchmark.run(pack_list or []) if pack_list is not None else None
        return {
            "quality_scores": scores.model_dump(),
            "benchmark": benchmark.model_dump() if benchmark else None,
        }
