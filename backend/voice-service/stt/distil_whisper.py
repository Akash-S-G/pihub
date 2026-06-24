from __future__ import annotations

from services.errors import not_configured
from .base import STTEngine, Transcript


class DistilWhisperSTTEngine(STTEngine):
    """Distil-Whisper Large-v3 adapter boundary.

    Production implementation should load the model once at startup and
    support partial transcripts. This placeholder keeps the API honest:
    STT is unavailable until the model runtime is configured.
    """

    async def transcribe(self, audio: bytes, language: str | None = None) -> Transcript:
        raise not_configured("Distil-Whisper Large-v3 STT")
