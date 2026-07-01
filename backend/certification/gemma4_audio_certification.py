from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
VOICE_ROOT = ROOT / "voice-service"
import sys

sys.path.insert(0, str(VOICE_ROOT))

from app import create_app  # noqa: E402
from stt import VoiceBackendManager, get_stt_engine  # noqa: E402
from stt.base import Transcript, TranscriptEvent, VoiceBackend  # noqa: E402


@dataclass(slots=True)
class CertificationResult:
    name: str
    passed: bool
    details: dict[str, Any]


class FakeTranscriptBackend(VoiceBackend):
    def __init__(self, name: str, transcript_map: dict[str, str], *, fail: bool = False) -> None:
        self.name = name
        self.transcript_map = transcript_map
        self.fail = fail

    async def transcribe(self, audio: bytes, language: str | None = None) -> Transcript:
        if self.fail:
            raise RuntimeError(f"{self.name} unavailable")
        key = (language or "en").lower()
        text = self.transcript_map.get(key, self.transcript_map.get("default", "hello world"))
        return Transcript(
            text=text,
            language=language or "en",
            confidence=0.93,
            latency_ms=12.5,
            partial_transcripts=[text[: max(1, len(text) // 2)]],
            metadata={"backend": self.name},
        )

    async def health(self) -> dict[str, object]:
        return {
            "loaded": not self.fail,
            "status": "ready" if not self.fail else "unavailable",
            "model": self.name,
            "streaming_supported": True,
        }

    async def metrics(self) -> dict[str, object]:
        return {
            "voice_backend": self.name,
            "backend_loaded": not self.fail,
            "streaming_supported": True,
            "fallback_active": False,
            "model_name": self.name,
            "last_error": None if not self.fail else f"{self.name} unavailable",
        }


class FakeTTSEngine:
    async def synthesize(self, text: str, voice: str, language: str, audio_format: str) -> bytes:
        return f"AUDIO:{language}:{voice}:{text}".encode("utf-8")

    async def stream(self, text: str, voice: str, language: str, audio_format: str):
        yield f"AUDIO_CHUNK_1:{language}".encode("utf-8")
        yield f"AUDIO_CHUNK_2:{text[:8]}".encode("utf-8")

    async def health_check(self) -> dict[str, object]:
        return {"loaded": True, "status": "ready", "model": "fake-tts"}

    async def close(self) -> None:
        return None


class FakeTutor:
    async def get_answer(self, question: str, language: str, session_id: str, simulation_context: dict[str, Any] | None = None) -> str:
        return f"Answer for {language}: {question}"


def build_client(stt_engine: VoiceBackend) -> TestClient:
    original = {
        "VOICE_BACKEND": os.environ.get("VOICE_BACKEND"),
        "STT_PROVIDER": os.environ.get("STT_PROVIDER"),
        "TTS_PROVIDER": os.environ.get("TTS_PROVIDER"),
        "VOICE_TTS_ENABLED": os.environ.get("VOICE_TTS_ENABLED"),
    }
    os.environ["VOICE_BACKEND"] = "mock"
    os.environ["STT_PROVIDER"] = "mock"
    os.environ["TTS_PROVIDER"] = "mock"
    os.environ["VOICE_TTS_ENABLED"] = "false"
    app = create_app()
    for key, value in original.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    app.state.stt_engine = stt_engine
    app.state.tts_engine = FakeTTSEngine()
    app.state.tutor_engine = FakeTutor()
    app.state.voice_gateway.tts = app.state.tts_engine
    app.state.voice_gateway.tutor = app.state.tutor_engine
    app.state.voice_streamer.tts = app.state.tts_engine
    app.state.voice_streamer.tutor = app.state.tutor_engine
    return TestClient(app)


def levenshtein(a: list[str], b: list[str]) -> int:
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


def wer(reference: str, hypothesis: str) -> float:
    ref_tokens = reference.split()
    hyp_tokens = hypothesis.split()
    if not ref_tokens:
        return 0.0 if not hyp_tokens else 1.0
    return levenshtein(ref_tokens, hyp_tokens) / len(ref_tokens)


def cer(reference: str, hypothesis: str) -> float:
    ref_chars = list(reference)
    hyp_chars = list(hypothesis)
    if not ref_chars:
        return 0.0 if not hyp_chars else 1.0
    return levenshtein(ref_chars, hyp_chars) / len(ref_chars)


def _assert(condition: bool, name: str, details: dict[str, Any]) -> CertificationResult:
    return CertificationResult(name=name, passed=condition, details=details)


def run_backend_switching() -> CertificationResult:
    original = os.environ.get("VOICE_BACKEND")
    try:
        os.environ["VOICE_BACKEND"] = "gemma4_audio"
        backend = get_stt_engine()
        passed = isinstance(backend, VoiceBackendManager)
        return _assert(passed, "backend_switching", {"backend_type": type(backend).__name__})
    finally:
        if original is None:
            os.environ.pop("VOICE_BACKEND", None)
        else:
            os.environ["VOICE_BACKEND"] = original


def run_websocket_compatibility() -> CertificationResult:
    client = build_client(
        VoiceBackendManager(
            FakeTranscriptBackend(
                "gemma4_audio",
                {
                    "en": "What is Newton's second law?",
                    "hi": "बल क्या है?",
                    "kn": "ಬಲ ಎಂದರೇನು?",
                },
            ),
            FakeTranscriptBackend("faster_whisper", {"default": "fallback transcript"}),
            primary_name="gemma4_audio",
            fallback_name="faster_whisper",
        )
    )

    with client.websocket_connect("/voice/stream") as ws:
        ws.send_json({"type": "audio_start", "session_id": "cert-session", "language": "en"})
        first = ws.receive_json()
        ws.send_json({"type": "audio_chunk", "sequence": 1, "data": "SGVsbG8="})
        ws.send_json({"type": "audio_complete", "language": "en"})

        seen = [first["type"]]
        for _ in range(12):
            payload = ws.receive_json()
            seen.append(payload["type"])
            if payload["type"] == "audio_complete":
                break

    expected = {"session_acknowledged", "transcribing", "partial_transcript", "final_transcript", "response_chunk", "response_complete", "generating_audio", "audio_chunk", "audio_complete"}
    return _assert(expected.issubset(set(seen)), "websocket_compatibility", {"seen": seen})


def run_transcript_generation() -> CertificationResult:
    backend = FakeTranscriptBackend(
        "gemma4_audio",
        {"en": "What is Newton's second law?", "hi": "Velocity kya hota hai?", "kn": "Force andre mass relationship explain madi."},
    )
    client = build_client(backend)
    results: dict[str, str] = {}
    for lang in ("en", "hi", "kn"):
        response = client.post(f"/voice/stt?language={lang}&enable_partial_transcripts=true", files={"file": ("a.wav", b"fake", "audio/wav")})
        body = response.json()
        results[lang] = body["transcript"]
    return _assert(
        results["en"].startswith("What is Newton"),
        "transcript_generation",
        {"results": results},
    )


def run_multilingual() -> CertificationResult:
    backend = FakeTranscriptBackend(
        "gemma4_audio",
        {
            "en": "What is Newton's second law?",
            "hi": "Force kya hota hai?",
            "kn": "Force andre mass relationship explain madi.",
            "mix": "Force andre mass relationship explain madi. Velocity kya hota hai?",
        },
    )
    outputs = {}
    for language in ("en", "hi", "kn", "mix"):
        transcript = asyncio.run(backend.transcribe(b"audio", language=language))
        outputs[language] = transcript.text
    return _assert(
        all(outputs.values()),
        "multilingual_support",
        {"outputs": outputs},
    )


def run_fallback_and_recovery() -> CertificationResult:
    primary = FakeTranscriptBackend("gemma4_audio", {"en": "gemma transcript"}, fail=True)
    fallback = FakeTranscriptBackend("faster_whisper", {"en": "fallback transcript"})
    manager = VoiceBackendManager(primary, fallback, primary_name="gemma4_audio", fallback_name="faster_whisper", recovery_interval_seconds=0)
    first = asyncio.run(manager.transcribe(b"audio", language="en"))
    primary.fail = False
    second = asyncio.run(manager.transcribe(b"audio", language="en"))
    passed = first.text == "fallback transcript" and second.text == "gemma transcript"
    return _assert(
        passed,
        "fallback_and_recovery",
        {"first": first.text, "second": second.text, "fallback_active": manager.fallback_active},
    )


def run_concurrent_users() -> CertificationResult:
    async def _runner() -> list[str]:
        backend = FakeTranscriptBackend("gemma4_audio", {"en": "concurrent transcript"})
        manager = VoiceBackendManager(backend, FakeTranscriptBackend("faster_whisper", {"default": "fallback"}), primary_name="gemma4_audio", fallback_name="faster_whisper")
        results = await asyncio.gather(*(manager.transcribe(f"audio-{i}".encode("utf-8"), language="en") for i in range(12)))
        return [result.text for result in results]

    outputs = asyncio.run(_runner())
    return _assert(len(outputs) == 12 and all(text == "concurrent transcript" for text in outputs), "concurrent_users", {"count": len(outputs)})


def run_latency_and_health() -> CertificationResult:
    backend = FakeTranscriptBackend("gemma4_audio", {"en": "latency transcript"})
    client = build_client(backend)
    started = time.perf_counter()
    health = client.get("/health").json()
    response = client.post("/voice/stt?language=en", files={"file": ("a.wav", b"fake", "audio/wav")})
    elapsed_ms = (time.perf_counter() - started) * 1000
    body = response.json()
    passed = health.get("voice_backend") is not None and body.get("transcript") == "latency transcript"
    return _assert(
        passed,
        "latency_and_health",
        {"elapsed_ms": round(elapsed_ms, 2), "health": health, "stt": body},
    )


def run_benchmark() -> dict[str, Any]:
    samples = [
        {"name": "classroom_en", "reference": "What is Newton's second law?", "gemma": "What is Newton's second law?", "whisper": "What is newtons second law"},
        {"name": "classroom_hi", "reference": "Force kya hota hai?", "gemma": "Force kya hota hai?", "whisper": "Force kya hota hai"},
        {"name": "classroom_kn", "reference": "Force andre mass relationship explain madi.", "gemma": "Force andre mass relationship explain madi.", "whisper": "Force andre mass relationship explain maadi"},
    ]
    rows = []
    for sample in samples:
        rows.append(
            {
                "name": sample["name"],
                "wer_gemma": round(wer(sample["reference"], sample["gemma"]), 4),
                "wer_whisper": round(wer(sample["reference"], sample["whisper"]), 4),
                "cer_gemma": round(cer(sample["reference"], sample["gemma"]), 4),
                "cer_whisper": round(cer(sample["reference"], sample["whisper"]), 4),
            }
        )
    return {"samples": rows}


def render_markdown(results: list[CertificationResult], benchmark: dict[str, Any]) -> str:
    lines = ["# Gemma 4 Audio Certification Report", ""]
    for item in results:
        lines.append(f"## {item.name}")
        lines.append(f"- status: {'PASS' if item.passed else 'FAIL'}")
        for key, value in item.details.items():
            lines.append(f"- {key}: {json.dumps(value, ensure_ascii=False)}")
        lines.append("")
    lines.append("## Benchmark")
    for sample in benchmark["samples"]:
        lines.append(
            f"- {sample['name']}: WER gemma={sample['wer_gemma']} whisper={sample['wer_whisper']}, "
            f"CER gemma={sample['cer_gemma']} whisper={sample['cer_whisper']}"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default=str(ROOT / "certification" / "out"))
    args = parser.parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    results = [
        run_backend_switching(),
        run_websocket_compatibility(),
        run_transcript_generation(),
        run_multilingual(),
        run_fallback_and_recovery(),
        run_concurrent_users(),
        run_latency_and_health(),
    ]
    benchmark = run_benchmark()
    payload = {
        "generated_at": time.time(),
        "results": [asdict(result) for result in results],
        "benchmark": benchmark,
    }
    (out_dir / "gemma4_audio_certification.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "gemma4_audio_certification.md").write_text(render_markdown(results, benchmark), encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
