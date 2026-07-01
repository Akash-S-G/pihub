from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from .base import Transcript, TranscriptEvent, VoiceBackend

logger = logging.getLogger(__name__)


class VoiceBackendManager(VoiceBackend):
    def __init__(
        self,
        primary: VoiceBackend,
        fallback: VoiceBackend,
        *,
        primary_name: str,
        fallback_name: str,
        recovery_interval_seconds: int = 60,
    ) -> None:
        self.primary = primary
        self.fallback = fallback
        self.primary_name = primary_name
        self.fallback_name = fallback_name
        self.recovery_interval_seconds = recovery_interval_seconds
        self.active_backend_name = primary_name
        self.fallback_active = False
        self.last_error: str | None = None
        self.last_switch_at = 0.0

    async def initialize(self) -> None:
        await self.primary.initialize()
        await self.fallback.initialize()

    def _should_try_primary(self) -> bool:
        if not self.fallback_active:
            return True
        return (time.perf_counter() - self.last_switch_at) >= self.recovery_interval_seconds

    def _activate_fallback(self, reason: str) -> None:
        self.fallback_active = True
        self.active_backend_name = self.fallback_name
        self.last_error = reason
        self.last_switch_at = time.perf_counter()
        logger.warning("VOICE_BACKEND_FALLBACK reason=%s", reason)

    def _activate_primary(self) -> None:
        self.fallback_active = False
        self.active_backend_name = self.primary_name
        self.last_error = None
        self.last_switch_at = time.perf_counter()

    async def _call_with_fallback(self, method: str, audio: bytes, language: str | None) -> Transcript:
        primary = getattr(self.primary, method)
        fallback = getattr(self.fallback, method)

        if self._should_try_primary():
            try:
                result = await primary(audio, language)
                self._activate_primary()
                return result
            except Exception as exc:
                self._activate_fallback(str(exc))

        try:
            return await fallback(audio, language)
        except Exception as exc:
            self.last_error = str(exc)
            raise

    async def transcribe(self, audio: bytes, language: str | None = None) -> Transcript:
        return await self._call_with_fallback("transcribe", audio, language)

    async def transcribe_stream(self, audio: bytes, language: str | None = None) -> AsyncIterator[TranscriptEvent]:
        backend = self.primary if self._should_try_primary() else self.fallback
        backend_name = self.primary_name if backend is self.primary else self.fallback_name
        try:
            async for event in backend.transcribe_stream(audio, language):
                event.metadata.setdefault("active_backend", backend_name)
                yield event
            if backend is self.primary:
                self._activate_primary()
        except Exception as exc:
            if backend is self.primary:
                self._activate_fallback(str(exc))
                transcript = await self.fallback.transcribe(audio, language)
                for partial in transcript.partial_transcripts:
                    yield TranscriptEvent(
                        type="partial_transcript",
                        text=partial,
                        language=transcript.language,
                        confidence=transcript.confidence,
                        metadata={"active_backend": self.fallback_name},
                    )
                yield TranscriptEvent(
                    type="final_transcript",
                    text=transcript.text,
                    language=transcript.language,
                    confidence=transcript.confidence,
                    metadata={"active_backend": self.fallback_name},
                )
            else:
                self.last_error = str(exc)
                raise

    async def health(self) -> dict[str, Any]:
        primary_health = await self.primary.health()
        fallback_health = await self.fallback.health()
        active = primary_health if self.active_backend_name == self.primary_name else fallback_health
        return {
            "voice_backend": self.active_backend_name,
            "backend_loaded": bool(active.get("loaded", False)),
            "streaming_supported": bool(active.get("streaming_supported", True)),
            "fallback_active": self.fallback_active,
            "model_name": active.get("model") or active.get("model_name"),
            "backend_latency": active.get("backend_latency"),
            "last_error": self.last_error or active.get("last_error"),
            "primary": primary_health,
            "fallback": fallback_health,
        }

    async def metrics(self) -> dict[str, Any]:
        primary_metrics = await self.primary.metrics()
        fallback_metrics = await self.fallback.metrics()
        return {
            "voice_backend": self.active_backend_name,
            "backend_loaded": not self.fallback_active,
            "streaming_supported": True,
            "fallback_active": self.fallback_active,
            "model_name": primary_metrics.get("model_name") or fallback_metrics.get("model_name"),
            "last_error": self.last_error,
            "primary": primary_metrics,
            "fallback": fallback_metrics,
        }

    async def shutdown(self) -> None:
        await self.primary.shutdown()
        await self.fallback.shutdown()
