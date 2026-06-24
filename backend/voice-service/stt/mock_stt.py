import os

class MockSTTEngine:
    def __init__(self):
        self.mock_text = os.getenv("MOCK_STT_TEXT", "What is photosynthesis?")

    async def transcribe(self, audio: bytes, language: str | None = None) -> dict[str, object]:
        return {
            "transcript": self.mock_text,
            "language": language or "en",
            "confidence": 0.95,
            "partial_transcripts": ["Processing..."]
        }
