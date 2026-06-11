from __future__ import annotations

from services.errors import not_configured
from services.interfaces import STTEngine


class DistilWhisperSTTEngine(STTEngine):
    """Distil-Whisper Large-v3 adapter boundary.

    Production implementation should load the model once at startup and
    support partial transcripts. This placeholder keeps the API honest:
    STT is unavailable until the model runtime is configured.
    """

    async def transcribe(self, audio: bytes, language: str | None = None) -> dict[str, object]:
        raise not_configured("Distil-Whisper Large-v3 STT")
