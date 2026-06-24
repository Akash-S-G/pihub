from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from .base import TTSEngine

class MockTTSEngine(TTSEngine):
    """Mock TTS implementation for local development and verification."""

    def __init__(self) -> None:
        self.dummy_wav = (
            b"RIFF\x24\x08\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"
            b"\x22\x56\x00\x00\x44\xac\x00\x00\x02\x00\x10\x00data\x00\x08\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00"
        )

    async def synthesize(self, text: str, voice: str, language: str, audio_format: str) -> bytes:
        return self.dummy_wav

    async def stream(self, text: str, voice: str, language: str, audio_format: str) -> AsyncIterator[bytes]:
        # Yield RIFF header then small chunks of dummy audio
        yield self.dummy_wav[:44]
        await asyncio.sleep(0.01)
        yield self.dummy_wav[44:]
