import os
from .base import STTEngine, Transcript

class MockSTTEngine(STTEngine):
    def __init__(self) -> None:
        self.mock_text = os.getenv("MOCK_STT_TEXT", "What is photosynthesis?")

    async def transcribe(self, audio: bytes, language: str | None = None) -> Transcript:
        return Transcript(
            text=self.mock_text,
            language=language or "en",
            confidence=0.95,
            latency_ms=10.0
        )
