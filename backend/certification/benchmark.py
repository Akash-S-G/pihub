from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Any

from .client import APIClient


DEFAULT_BENCHMARK_QUESTIONS: list[dict[str, Any]] = [
    {"question": "What is evaporation?", "grade": 6, "subject": "science", "chapter": "evaporation", "topic": "evaporation"},
    {"question": "Explain photosynthesis.", "grade": 6, "subject": "science", "chapter": "photosynthesis", "topic": "photosynthesis"},
    {"question": "What is the water cycle?", "grade": 6, "subject": "science", "chapter": "water cycle", "topic": "water cycle"},
    {"question": "What is proportional reasoning?", "grade": 8, "subject": "mathematics", "chapter": "proportional reasoning", "topic": "proportional reasoning"},
    {"question": "Explain democracy.", "grade": 8, "subject": "social science", "chapter": "democracy", "topic": "democracy"},
] * 20


@dataclass
class BenchmarkResult:
    avg_latency_ms: float
    p95_latency_ms: float
    retrieval_success_rate: float
    context_usage_rate: float
    hallucination_rate: float
    samples: list[dict[str, Any]]


class DemoReadinessBenchmark:
    def __init__(self, client: APIClient) -> None:
        self.client = client

    def run(self, questions: list[dict[str, Any]] | None = None) -> BenchmarkResult:
        questions = questions or DEFAULT_BENCHMARK_QUESTIONS
        latencies: list[float] = []
        retrieval_success = 0
        context_usage = 0
        hallucination_flags = 0
        samples: list[dict[str, Any]] = []

        for index, item in enumerate(questions, start=1):
            payload = dict(item)
            payload["stream"] = False
            payload["sessionState"] = {"session_id": f"benchmark-{index}"}
            response = self._timed_tutor(payload)
            latencies.append(response["latency_ms"])
            debug = response["debug"]
            answer = response["answer"]
            context = response["context"]
            evaluation = self.client.post_json(
                "/ai/tutor/evaluate",
                {
                    "question": payload["question"],
                    "answer": answer,
                    "context": context,
                    "language": payload.get("language") or "en",
                    "grade": payload.get("grade"),
                },
            )
            has_retrieval = int(debug.get("retrieval_diagnostics", {}).get("chunks_retrieved") or 0) > 0 or len(context) > 0
            context_used = bool(evaluation.get("context_used"))
            hallucination = str(evaluation.get("hallucination_risk") or "low")
            retrieval_success += 1 if has_retrieval else 0
            context_usage += 1 if context_used else 0
            hallucination_flags += 1 if hallucination == "high" else 0
            samples.append({
                "index": index,
                "question": payload["question"],
                "latency_ms": response["latency_ms"],
                "retrieved_chunks": len(context),
                "context_used": context_used,
                "hallucination_risk": hallucination,
                "language_correct": bool(evaluation.get("language_correct")),
                "grade_appropriate": bool(evaluation.get("grade_appropriate")),
            })

        return BenchmarkResult(
            avg_latency_ms=round(statistics.mean(latencies), 2) if latencies else 0.0,
            p95_latency_ms=round(_percentile(latencies, 95), 2) if latencies else 0.0,
            retrieval_success_rate=round((retrieval_success / len(questions)) * 100, 2) if questions else 0.0,
            context_usage_rate=round((context_usage / len(questions)) * 100, 2) if questions else 0.0,
            hallucination_rate=round((hallucination_flags / len(questions)) * 100, 2) if questions else 0.0,
            samples=samples,
        )

    def _timed_tutor(self, payload: dict[str, Any]) -> dict[str, Any]:
        import time

        started = time.perf_counter()
        debug = self.client.post_json("/ai/tutor", payload)
        latency_ms = (time.perf_counter() - started) * 1000
        answer = str(debug.get("answer") or "")
        context = debug.get("context") if isinstance(debug.get("context"), list) else []
        return {"latency_ms": latency_ms, "debug": debug, "answer": answer, "context": context}


def _percentile(values: list[float], percentile: int) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    idx = min(len(ordered) - 1, round((percentile / 100) * (len(ordered) - 1)))
    return ordered[idx]
