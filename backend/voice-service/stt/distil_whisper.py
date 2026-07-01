from __future__ import annotations

from services.errors import not_configured
from .base import Transcript, VoiceBackend


class DistilWhisperSTTEngine(VoiceBackend):
    """Distil-Whisper Large-v3 adapter boundary.

    Production implementation should load the model once at startup and
    support partial transcripts. This placeholder keeps the API honest:
    STT is unavailable until the model runtime is configured.
    """

    async def transcribe(self, audio: bytes, language: str | None = None) -> Transcript:
        raise not_configured("Distil-Whisper Large-v3 STT")

    async def health(self) -> dict[str, object]:
        return {"loaded": False, "status": "unavailable", "model": "distil-whisper"}
