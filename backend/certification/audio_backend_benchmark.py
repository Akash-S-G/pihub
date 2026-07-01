from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import psutil

ROOT = Path(__file__).resolve().parents[2]
VOICE_ROOT = ROOT / "backend" / "voice-service"

import sys

sys.path.insert(0, str(VOICE_ROOT))

from stt import FasterWhisperBackend, Gemma4AudioBackend  # noqa: E402
from stt.base import Transcript, VoiceBackend  # noqa: E402


@dataclass(slots=True)
class Sample:
    name: str
    audio_path: Path
    reference: str
    language: str = "en"
    scenario: str = "clean"
    tags: list[str] | None = None


@dataclass(slots=True)
class SampleResult:
    sample: str
    backend: str
    language: str
    scenario: str
    reference: str
    hypothesis: str
    wer: float
    cer: float
    first_partial_ms: float | None
    final_latency_ms: float | None
    cpu_percent: float | None
    ram_mb: float | None
    partial_count: int
    confidence: float | None
    metadata: dict[str, Any]


@dataclass(slots=True)
class BackendSummary:
    backend: str
    model_load_ms: float | None
    avg_wer: float
    avg_cer: float
    avg_first_partial_ms: float | None
    avg_final_latency_ms: float | None
    avg_cpu_percent: float | None
    avg_ram_mb: float | None
    concurrency: int
    concurrent_duration_ms: float | None
    total_samples: int
    breakdown: dict[str, Any]


def _levenshtein(a: list[str], b: list[str]) -> int:
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, token_a in enumerate(a, start=1):
        curr = [i]
        for j, token_b in enumerate(b, start=1):
            cost = 0 if token_a == token_b else 1
            curr.append(min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost))
        prev = curr
    return prev[-1]


def word_error_rate(reference: str, hypothesis: str) -> float:
    ref = reference.split()
    hyp = hypothesis.split()
    if not ref:
        return 0.0 if not hyp else 1.0
    return _levenshtein(ref, hyp) / len(ref)


def char_error_rate(reference: str, hypothesis: str) -> float:
    ref = list(reference)
    hyp = list(hypothesis)
    if not ref:
        return 0.0 if not hyp else 1.0
    return _levenshtein(ref, hyp) / len(ref)


def _mean(values: list[float | None]) -> float | None:
    filtered = [value for value in values if value is not None]
    if not filtered:
        return None
    return round(statistics.mean(filtered), 2)


def load_manifest(path: Path) -> list[Sample]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [
        Sample(
            name=str(item["name"]),
            audio_path=(path.parent / item["audio_path"]).resolve(),
            reference=str(item["reference"]),
            language=str(item.get("language", "en")),
            scenario=str(item.get("scenario", "clean")),
            tags=list(item.get("tags") or []),
        )
        for item in payload
    ]


async def _ensure_loaded(backend: VoiceBackend) -> float | None:
    started = time.perf_counter()
    await backend.initialize()
    health = await backend.health()
    load_ms = health.get("backend_latency")
    if isinstance(load_ms, (int, float)):
        return float(load_ms)
    return round((time.perf_counter() - started) * 1000, 2)


async def benchmark_sample(backend: VoiceBackend, sample: Sample) -> SampleResult:
    audio = sample.audio_path.read_bytes()
    process = psutil.Process()
    cpu_before = process.cpu_percent(interval=None)
    mem_before = process.memory_info().rss / (1024 * 1024)

    started = time.perf_counter()
    first_partial_ms: float | None = None
    partial_count = 0
    final: Transcript | None = None

    async for event in backend.transcribe_stream(audio, sample.language):
        elapsed_ms = (time.perf_counter() - started) * 1000
        if event.type == "partial_transcript":
            partial_count += 1
            if first_partial_ms is None:
                first_partial_ms = round(elapsed_ms, 2)
        elif event.type == "final_transcript":
            final = Transcript(
                text=event.text,
                language=event.language or sample.language,
                confidence=event.confidence,
                latency_ms=round(elapsed_ms, 2),
                metadata=dict(event.metadata),
            )

    if final is None:
        final = await backend.transcribe(audio, sample.language)

    cpu_after = process.cpu_percent(interval=None)
    mem_after = process.memory_info().rss / (1024 * 1024)

    return SampleResult(
        sample=sample.name,
        backend=backend.__class__.__name__,
        language=sample.language,
        scenario=sample.scenario,
        reference=sample.reference,
        hypothesis=final.text,
        wer=round(word_error_rate(sample.reference, final.text), 4),
        cer=round(char_error_rate(sample.reference, final.text), 4),
        first_partial_ms=first_partial_ms,
        final_latency_ms=round(final.latency_ms, 2) if final.latency_ms else round((time.perf_counter() - started) * 1000, 2),
        cpu_percent=round((cpu_before + cpu_after) / 2.0, 2),
        ram_mb=round(max(mem_before, mem_after), 2),
        partial_count=partial_count,
        confidence=final.confidence,
        metadata=dict(final.metadata),
    )


async def benchmark_concurrency(backend: VoiceBackend, samples: list[Sample], concurrency: int) -> dict[str, Any]:
    started = time.perf_counter()
    subset = samples[:concurrency]
    results = await asyncio.gather(*(benchmark_sample(backend, sample) for sample in subset))
    return {
        "concurrency": concurrency,
        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        "avg_wer": round(statistics.mean([result.wer for result in results]), 4) if results else None,
        "avg_cer": round(statistics.mean([result.cer for result in results]), 4) if results else None,
        "results": [asdict(result) for result in results],
    }


def summarize_backend(backend_name: str, load_ms: float | None, results: list[SampleResult], concurrency: dict[str, Any]) -> BackendSummary:
    def _group(field: str) -> dict[str, dict[str, float]]:
        grouped: dict[str, list[SampleResult]] = {}
        for result in results:
            key = getattr(result, field)
            grouped.setdefault(key, []).append(result)
        return {
            key: {
                "avg_wer": round(statistics.mean([item.wer for item in items]), 4),
                "avg_cer": round(statistics.mean([item.cer for item in items]), 4),
                "avg_first_partial_ms": _mean([item.first_partial_ms for item in items]),
                "avg_final_latency_ms": _mean([item.final_latency_ms for item in items]),
            }
            for key, items in grouped.items()
        }

    return BackendSummary(
        backend=backend_name,
        model_load_ms=load_ms,
        avg_wer=round(statistics.mean([result.wer for result in results]), 4) if results else 0.0,
        avg_cer=round(statistics.mean([result.cer for result in results]), 4) if results else 0.0,
        avg_first_partial_ms=_mean([result.first_partial_ms for result in results]),
        avg_final_latency_ms=_mean([result.final_latency_ms for result in results]),
        avg_cpu_percent=_mean([result.cpu_percent for result in results]),
        avg_ram_mb=_mean([result.ram_mb for result in results]),
        concurrency=int(concurrency["concurrency"]),
        concurrent_duration_ms=float(concurrency["duration_ms"]) if concurrency.get("duration_ms") is not None else None,
        total_samples=len(results),
        breakdown={
            "samples": [asdict(result) for result in results],
            "concurrency_test": concurrency,
            "by_language": _group("language"),
            "by_scenario": _group("scenario"),
        },
    )


def render_markdown(summaries: list[BackendSummary]) -> str:
    fast = next(summary for summary in summaries if summary.backend == "FasterWhisperBackend")
    gemma = next(summary for summary in summaries if summary.backend == "Gemma4AudioBackend")
    lines = ["# Audio Backend Benchmark Report", ""]
    lines.append("| Metric | Faster-Whisper | Gemma 4 Audio |")
    lines.append("| --- | ---: | ---: |")
    rows = [
        ("WER", fast.avg_wer, gemma.avg_wer),
        ("CER", fast.avg_cer, gemma.avg_cer),
        ("Time to first partial", fast.avg_first_partial_ms, gemma.avg_first_partial_ms),
        ("Final transcript latency", fast.avg_final_latency_ms, gemma.avg_final_latency_ms),
        ("CPU usage", fast.avg_cpu_percent, gemma.avg_cpu_percent),
        ("RAM usage", fast.avg_ram_mb, gemma.avg_ram_mb),
        ("Model load time", fast.model_load_ms, gemma.model_load_ms),
        ("Concurrent sessions", fast.concurrent_duration_ms, gemma.concurrent_duration_ms),
    ]
    for label, fast_value, gemma_value in rows:
        lines.append(f"| {label} | {fast_value} | {gemma_value} |")
    lines.append("")
    for summary in summaries:
        lines.append(f"## {summary.backend}")
        lines.append(f"- samples: {summary.total_samples}")
        lines.append(f"- avg_wer: {summary.avg_wer}")
        lines.append(f"- avg_cer: {summary.avg_cer}")
        lines.append(f"- avg_first_partial_ms: {summary.avg_first_partial_ms}")
        lines.append(f"- avg_final_latency_ms: {summary.avg_final_latency_ms}")
        lines.append(f"- avg_cpu_percent: {summary.avg_cpu_percent}")
        lines.append(f"- avg_ram_mb: {summary.avg_ram_mb}")
        lines.append(f"- model_load_ms: {summary.model_load_ms}")
        lines.append(f"- concurrent_duration_ms: {summary.concurrent_duration_ms}")
        lines.append(f"- breakdown: {json.dumps(summary.breakdown, ensure_ascii=False)}")
        lines.append("")
    return "\n".join(lines)


async def run(args: argparse.Namespace) -> int:
    samples = load_manifest(Path(args.manifest))
    if not samples:
        raise ValueError("manifest contained no samples")

    backends: list[VoiceBackend] = [FasterWhisperBackend(), Gemma4AudioBackend()]
    summaries: list[BackendSummary] = []

    for backend in backends:
        load_ms = await _ensure_loaded(backend)
        per_sample = [await benchmark_sample(backend, sample) for sample in samples]
        concurrency = await benchmark_concurrency(backend, samples, min(args.concurrency, len(samples)))
        summaries.append(summarize_backend(backend.__class__.__name__, load_ms, per_sample, concurrency))
        await backend.shutdown()

    payload = {
        "generated_at": time.time(),
        "manifest": str(Path(args.manifest).resolve()),
        "summaries": [asdict(summary) for summary in summaries],
    }

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "audio_backend_benchmark.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "audio_backend_benchmark.md").write_text(render_markdown(summaries), encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare Faster-Whisper with Gemma 4 Audio.")
    parser.add_argument("--manifest", required=True, help="JSON manifest with audio_path, reference, language, scenario")
    parser.add_argument("--out-dir", default=str(ROOT / "backend" / "certification" / "out"))
    parser.add_argument("--concurrency", type=int, default=4)
    args = parser.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
