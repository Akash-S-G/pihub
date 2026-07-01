import os

from .base import Transcript, VoiceBackend


class MockSTTEngine(VoiceBackend):
    def __init__(self):
        self.mock_text = os.getenv("MOCK_STT_TEXT", "What is photosynthesis?")

    async def transcribe(self, audio: bytes, language: str | None = None) -> Transcript:
        return Transcript(
            text=self.mock_text,
            language=language or "en",
            confidence=0.95,
            latency_ms=10.0,
            partial_transcripts=["Processing..."],
            metadata={"backend": "mock"},
        )

    async def health(self) -> dict[str, object]:
        return {"loaded": True, "status": "mock", "model": "mock"}
