from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

class TTSEngine(ABC):
    @abstractmethod
    async def synthesize(self, text: str, voice: str, language: str, audio_format: str) -> bytes:
        """Text to audio interface."""

    @abstractmethod
    async def stream(self, text: str, voice: str, language: str, audio_format: str) -> AsyncIterator[bytes]:
        """Chunked TTS stream interface."""
