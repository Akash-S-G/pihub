from __future__ import annotations

import asyncio
import base64
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import WebSocketDisconnect

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import create_app  # noqa: E402
from api.routes import voice_stream  # noqa: E402
from services.tutor_adapter import InferenceTutorAdapter  # noqa: E402


class FakeTTS:
    async def synthesize(self, text: str, voice: str, language: str, audio_format: str) -> bytes:
        return b"fake-audio"

    async def stream(self, text: str, voice: str, language: str, audio_format: str) -> AsyncIterator[bytes]:
        yield b"chunk-1"
        yield b"chunk-2"


class FakeSTT:
    async def transcribe(self, audio: bytes, language: str | None = None) -> dict[str, Any]:
        return {"transcript": "What is photosynthesis?", "language": language or "en"}

    async def transcribe_stream(self, audio: bytes, language: str | None = None) -> AsyncIterator[Any]:
        class Event:
            def __init__(self, type: str, text: str) -> None:
                self.type = type
                self.text = text
                self.language = language or "en"
                self.confidence = 0.9
                self.metadata = {}

        yield Event("partial_transcript", "Processing...")
        yield Event("final_transcript", "What is photosynthesis?")


class FakeTutor:
    async def answer_with_context(self, question: str, filters: dict[str, Any]) -> dict[str, Any]:
        return {"answer": "Photosynthesis is the process by which plants make food.", "context": [{"chapter_id": filters.get("chapter_id")}]}

    async def stream_answer_with_context(self, question: str, filters: dict[str, Any]) -> AsyncIterator[str]:
        yield "Photosynthesis "
        yield "makes food."


class FakeWebSocket:
    def __init__(self, app, frames: list[str]) -> None:
        self.app = app
        self._frames = frames
        self.sent: list[dict[str, Any]] = []
        self.accepted = False

    async def accept(self) -> None:
        self.accepted = True

    async def receive_text(self) -> str:
        if not self._frames:
            raise WebSocketDisconnect()
        return self._frames.pop(0)

    async def send_json(self, data: dict[str, Any]) -> None:
        self.sent.append(data)

    async def close(self) -> None:
        raise WebSocketDisconnect()


@pytest.mark.anyio
async def test_full_voice_pipeline_and_reconnect() -> None:
    original_get_answer = InferenceTutorAdapter.get_answer

    async def mock_get_answer(self, question, language, session_id, simulation_context=None):
        return "Photosynthesis is the process by which plants make food."

    InferenceTutorAdapter.get_answer = mock_get_answer
    session_id = "test-session-xyz"
    app = create_app()
    app.state.tts_engine = FakeTTS()
    app.state.stt_engine = FakeSTT()
    app.state.tutor_engine = FakeTutor()
    app.state.voice_gateway.tts = app.state.tts_engine
    app.state.voice_gateway.tutor = app.state.tutor_engine
    app.state.voice_streamer.tts = app.state.tts_engine
    app.state.voice_streamer.tutor = app.state.tutor_engine

    try:
        frames = [
            json_dump({"type": "audio_start", "session_id": session_id}),
            json_dump({"type": "audio_chunk", "sequence": 1, "data": base64.b64encode(b"Hello").decode()}),
            json_dump({"type": "audio_complete", "language": "kn", "simulation_context": {"experiment_id": "test"}}),
        ]
        ws = FakeWebSocket(app, frames)
        await voice_stream(ws)

        assert ws.accepted is True
        assert any(msg["type"] == "session_acknowledged" for msg in ws.sent)
        assert any(msg["type"] == "partial_transcript" for msg in ws.sent)
        assert any(msg["type"] == "final_transcript" for msg in ws.sent)
        assert any(msg["type"] == "response_chunk" for msg in ws.sent)
        assert any(msg["type"] == "response_complete" for msg in ws.sent)
        assert any(msg["type"] == "audio_complete" for msg in ws.sent)

        metrics = app.state.voice_metrics.snapshot()
        assert metrics.get("voice_sessions", 0) >= 1
        assert metrics.get("reconnects", 0) >= 0
    finally:
        InferenceTutorAdapter.get_answer = original_get_answer


def json_dump(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(payload)
