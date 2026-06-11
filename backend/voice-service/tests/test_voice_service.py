from __future__ import annotations

import sys
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import create_app  # noqa: E402


class FakeTTS:
    async def synthesize(self, text: str, voice: str, language: str, audio_format: str) -> bytes:
        return f"AUDIO:{language}:{voice}:{text}".encode("utf-8")

    async def stream(self, text: str, voice: str, language: str, audio_format: str) -> AsyncIterator[bytes]:
        yield b"AUDIO_CHUNK_1"
        yield b"AUDIO_CHUNK_2"


class FakeSTT:
    async def transcribe(self, audio: bytes, language: str | None = None) -> dict[str, Any]:
        return {"transcript": "what is photosynthesis", "language": language or "en", "confidence": 0.9, "partial_transcripts": ["what is"]}


class FakeTutor:
    async def answer_with_context(self, question: str, filters: dict[str, Any]) -> dict[str, Any]:
        return {"answer": "Photosynthesis helps plants make food.", "context": [{"chapter_id": filters.get("chapter_id")}]}

    async def stream_answer_with_context(self, question: str, filters: dict[str, Any]) -> AsyncIterator[str]:
        yield "Photosynthesis "
        yield "makes food."


def client() -> TestClient:
    app = create_app()
    app.state.tts_engine = FakeTTS()
    app.state.stt_engine = FakeSTT()
    app.state.tutor_engine = FakeTutor()
    app.state.voice_gateway.tts = app.state.tts_engine
    app.state.voice_gateway.tutor = app.state.tutor_engine
    app.state.voice_streamer.tts = app.state.tts_engine
    app.state.voice_streamer.tutor = app.state.tutor_engine
    return TestClient(app)


def test_tts_cache_miss_then_hit() -> None:
    c = client()
    payload = {"text": "Hello", "language": "en", "cache": True}
    first = c.post("/voice/tts", json=payload)
    second = c.post("/voice/tts", json=payload)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["cache_status"] == "miss"
    assert second.json()["cache_status"] == "hit"


def test_audio_retrieval_and_range_request() -> None:
    c = client()
    created = c.post("/voice/tts", json={"text": "Range me"}).json()
    full = c.get(created["audio_url"])
    partial = c.get(created["audio_url"], headers={"Range": "bytes=0-4"})
    assert full.status_code == 200
    assert full.headers["accept-ranges"] == "bytes"
    assert partial.status_code == 206
    assert partial.content == full.content[:5]


def test_voice_query_cache_miss() -> None:
    c = client()
    response = c.post("/voice/query", json={"question": "What is photosynthesis?", "chapter_id": "plants"})
    assert response.status_code == 200
    body = response.json()
    assert body["response_source"] == "rag_tutor"
    assert body["audio_url"].startswith("/voice/audio/")


def test_stt_request() -> None:
    c = client()
    response = c.post("/voice/stt?language=en&enable_partial_transcripts=true", files={"file": ("q.wav", b"fake", "audio/wav")})
    assert response.status_code == 200
    assert response.json()["transcript"] == "what is photosynthesis"


def test_streaming_tts() -> None:
    c = client()
    response = c.post("/voice/tts", json={"text": "stream", "stream": True})
    assert response.status_code == 200
    assert b"AUDIO_CHUNK" in response.content
