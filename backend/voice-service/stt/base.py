from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Transcript:
    text: str
    language: str
    confidence: float | None
    latency_ms: float
    partial_transcripts: list[str] = field(default_factory=list)
    timestamps: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TranscriptEvent:
    type: str
    text: str
    language: str | None = None
    confidence: float | None = None
    timestamp_ms: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class VoiceBackend(ABC):
    async def initialize(self) -> None:
        """Initialize the backend if it needs a warm start."""

    @abstractmethod
    async def transcribe(self, audio: bytes, language: str | None = None) -> Transcript:
        """Return the final transcript for a complete audio buffer."""

    async def transcribe_stream(self, audio: bytes, language: str | None = None) -> AsyncIterator[TranscriptEvent]:
        """Yield partial and final transcript events for streaming callers."""
        transcript = await self.transcribe(audio, language)
        for partial in transcript.partial_transcripts:
            yield TranscriptEvent(type="partial_transcript", text=partial, language=transcript.language)
        yield TranscriptEvent(
            type="final_transcript",
            text=transcript.text,
            language=transcript.language,
            confidence=transcript.confidence,
        )

    async def health(self) -> dict[str, Any]:
        return {"loaded": True, "status": "ready"}

    async def metrics(self) -> dict[str, Any]:
        return {}

    async def shutdown(self) -> None:
        """Release backend resources."""


STTEngine = VoiceBackend
