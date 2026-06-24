from __future__ import annotations

import sys
import json
import asyncio
from pathlib import Path
from typing import Any, AsyncIterator
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import create_app  # noqa: E402
from services.tutor_adapter import InferenceTutorAdapter

class FakeTTS:
    async def synthesize(self, text: str, voice: str, language: str, audio_format: str) -> bytes:
        return b"fake-audio"
    async def stream(self, text: str, voice: str, language: str, audio_format: str) -> AsyncIterator[bytes]:
        yield b"chunk"

class FakeSTT:
    async def transcribe(self, audio: bytes, language: str | None = None) -> dict[str, Any]:
        return {"transcript": "What is photosynthesis?", "language": language or "en"}

def test_full_voice_pipeline_and_reconnect(client: TestClient) -> None:
    # Patch get_answer to return a mock answer without calling the network
    original_get_answer = InferenceTutorAdapter.get_answer
    async def mock_get_answer(self, question, language, session_id, simulation_context=None):
        return "Photosynthesis is the process by which plants make food."
    
    InferenceTutorAdapter.get_answer = mock_get_answer

    session_id = "test-session-xyz"

    try:
        # 1. Establish first connection
        with client.websocket_connect("/voice/stream") as ws:
            # Client -> Server: audio_start
            ws.send_json({"type": "audio_start", "session_id": session_id})
            resp = ws.receive_json()
            assert resp["type"] == "session_acknowledged"
            assert resp["session_id"] == session_id

            # Client -> Server: audio_chunk
            ws.send_json({"type": "audio_chunk", "sequence": 1, "data": "SGVsbG8="})

            # Client -> Server: audio_complete
            ws.send_json({
                "type": "audio_complete",
                "language": "kn",
                "simulation_context": {"experiment_id": "test"}
            })

            # Server -> Client: partial_transcript
            resp = ws.receive_json()
            assert resp["type"] == "partial_transcript"
            assert resp["text"] == "Processing..."

            # Server -> Client: final_transcript
            resp = ws.receive_json()
            assert resp["type"] == "final_transcript"
            assert resp["text"] == "What is photosynthesis?"

            # Server -> Client: response_chunks
            chunks = []
            while True:
                resp = ws.receive_json()
                if resp["type"] == "response_complete":
                    break
                assert resp["type"] == "response_chunk"
                chunks.append(resp["text"])
            
            assert len(chunks) > 0
            assert "Photosynthesis" in "".join(chunks)

            # Server -> Client: audio_ready
            resp = ws.receive_json()
            assert resp["type"] == "audio_ready"
            assert resp["audio_url"] == "/mock/audio.wav"

        # 2. Establish second connection (reconnect) with same session_id
        with client.websocket_connect("/voice/stream") as ws2:
            ws2.send_json({"type": "audio_start", "session_id": session_id})
            resp = ws2.receive_json()
            assert resp["type"] == "session_acknowledged"
            assert resp["session_id"] == session_id

        # 3. Verify metrics
        metrics_resp = client.get("/voice/metrics")
        assert metrics_resp.status_code == 200
        metrics = metrics_resp.json()
        assert metrics.get("voice_sessions") is not None
        assert metrics.get("reconnects", 0) >= 1
        print("ALL TESTS PASSED SUCCESSFULLY!")
        
    finally:
        InferenceTutorAdapter.get_answer = original_get_answer

if __name__ == "__main__":
    app = create_app()
    app.state.tts_engine = FakeTTS()
    app.state.stt_engine = FakeSTT()
    client = TestClient(app)
    test_full_voice_pipeline_and_reconnect(client)
