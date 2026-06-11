from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any


class STTEngine(ABC):
    @abstractmethod
    async def transcribe(self, audio: bytes, language: str | None = None) -> dict[str, Any]:
        """Speech to text. Implementations may use Distil-Whisper Large-v3."""


class TTSEngine(ABC):
    @abstractmethod
    async def synthesize(self, text: str, voice: str, language: str, audio_format: str) -> bytes:
        """Text to audio. Implementations may use Svara TTS Q3_K_S via llama.cpp."""

    @abstractmethod
    async def stream(self, text: str, voice: str, language: str, audio_format: str) -> AsyncIterator[bytes]:
        """Chunked TTS stream."""


class TutorEngine(ABC):
    @abstractmethod
    async def answer_with_context(self, question: str, filters: dict[str, Any]) -> dict[str, Any]:
        """Gemma 4 12B tutor over curriculum RAG. Must return no answer without context."""

    @abstractmethod
    async def stream_answer_with_context(self, question: str, filters: dict[str, Any]) -> AsyncIterator[str]:
        """Streaming tutor answer chunks over curriculum RAG."""
