from __future__ import annotations

import asyncio

from stt.base import Transcript, VoiceBackend
from stt.manager import VoiceBackendManager


class PrimaryUnavailableBackend(VoiceBackend):
    def __init__(self) -> None:
        self.loaded = False
        self.last_error = "Gemma runtime dependencies unavailable"

    async def initialize(self) -> None:
        self.loaded = False

    async def transcribe(self, audio: bytes, language: str | None = None) -> Transcript:
        raise RuntimeError("primary unavailable")

    async def health(self) -> dict[str, object]:
        return {
            "loaded": self.loaded,
            "status": "unavailable",
            "last_error": self.last_error,
            "model": "google/gemma-4-E4B-it",
        }


class HealthyFallbackBackend(VoiceBackend):
    def __init__(self) -> None:
        self.loaded = False

    async def initialize(self) -> None:
        self.loaded = True

    async def transcribe(self, audio: bytes, language: str | None = None) -> Transcript:
        return Transcript(text="fallback transcript", language=language or "en", confidence=1.0, latency_ms=1.0)

    async def health(self) -> dict[str, object]:
        return {
            "loaded": self.loaded,
            "status": "ready",
            "model": "fallback",
        }


def test_manager_activates_fallback_when_primary_is_unavailable() -> None:
    manager = VoiceBackendManager(
        PrimaryUnavailableBackend(),
        HealthyFallbackBackend(),
        primary_name="gemma4_audio",
        fallback_name="faster_whisper",
        recovery_interval_seconds=0,
    )

    asyncio.run(manager.initialize())
    health = asyncio.run(manager.health())

    assert manager.fallback_active is True
    assert manager.active_backend_name == "faster_whisper"
    assert health["voice_backend"] == "faster_whisper"
    assert health["backend_loaded"] is True
    assert "Gemma runtime dependencies unavailable" in str(health["last_error"])
