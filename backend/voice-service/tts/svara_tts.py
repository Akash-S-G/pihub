from __future__ import annotations

from collections.abc import AsyncIterator

from services.errors import not_configured
from services.interfaces import TTSEngine


class SvaraTTSEngine(TTSEngine):
    """Svara TTS Q3_K_S llama.cpp adapter boundary."""

    async def synthesize(self, text: str, voice: str, language: str, audio_format: str) -> bytes:
        raise not_configured("Svara TTS Q3_K_S")

    async def stream(self, text: str, voice: str, language: str, audio_format: str) -> AsyncIterator[bytes]:
        raise not_configured("Svara TTS Q3_K_S streaming")
        yield b""
