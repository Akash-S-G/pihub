from __future__ import annotations

import asyncio
import os
import tempfile
import time
import logging
from collections.abc import AsyncIterator

from .base import Transcript, TranscriptEvent, VoiceBackend

logger = logging.getLogger(__name__)


class FasterWhisperBackend(VoiceBackend):
    _model_instance = None

    def __init__(self) -> None:
        self.model_size = os.getenv("WHISPER_MODEL", "small")
        self.device = os.getenv("WHISPER_DEVICE", "cpu")
        self.compute_type = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
        self.last_error: str | None = None
        self.loaded = False
        self.load_time_ms: float | None = None

    async def initialize(self) -> None:
        if self.model is not None:
            self.loaded = True
            return
        started = time.perf_counter()
        try:
            await asyncio.to_thread(self._load_model)
            self.load_time_ms = (time.perf_counter() - started) * 1000
            self.loaded = self.model is not None
        except Exception:
            self.loaded = False
            raise

    def _load_model(self) -> None:
        if FasterWhisperBackend._model_instance is not None:
            self.loaded = True
            return
        try:
            from faster_whisper import WhisperModel

            logger.info(
                "Loading Faster Whisper model '%s' on %s with compute type %s",
                self.model_size,
                self.device,
                self.compute_type,
            )
            FasterWhisperBackend._model_instance = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
                download_root="/models",
            )
            logger.info("Faster Whisper model loaded successfully")
            self.loaded = True
        except Exception as exc:
            self.last_error = str(exc)
            logger.error("Failed to load Faster Whisper model: %s", exc)
            raise

    @property
    def model(self):
        return FasterWhisperBackend._model_instance

    async def transcribe(self, audio: bytes, language: str | None = None) -> Transcript:
        if self.model is None:
            await self.initialize()
        if self.model is None:
            raise RuntimeError(self.last_error or "Faster Whisper model is not loaded")
        started = time.perf_counter()

        def run_transcribe() -> tuple[str, object, list[str], list[dict[str, object]]]:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
                tmp.write(audio)
                tmp.flush()

                kwargs: dict[str, object] = {}
                if language:
                    kwargs["language"] = language

                segments, info = self.model.transcribe(tmp.name, beam_size=5, **kwargs)
                collected: list[str] = []
                partials: list[str] = []
                timestamps: list[dict[str, object]] = []
                for segment in segments:
                    text = (segment.text or "").strip()
                    if not text:
                        continue
                    collected.append(text)
                    partials.append(" ".join(collected).strip())
                    timestamps.append(
                        {
                            "start": getattr(segment, "start", None),
                            "end": getattr(segment, "end", None),
                            "text": text,
                        }
                    )
                return " ".join(collected).strip(), info, partials, timestamps

        loop = asyncio.get_running_loop()
        text, info, partials, timestamps = await loop.run_in_executor(None, run_transcribe)
        latency_ms = (time.perf_counter() - started) * 1000

        return Transcript(
            text=text,
            language=str(getattr(info, "language", language or "en") or language or "en"),
            confidence=getattr(info, "language_probability", None),
            latency_ms=latency_ms,
            partial_transcripts=partials,
            timestamps=timestamps,
            metadata={"backend": "faster_whisper"},
        )

    async def transcribe_stream(self, audio: bytes, language: str | None = None) -> AsyncIterator[TranscriptEvent]:
        transcript = await self.transcribe(audio, language)
        for partial in transcript.partial_transcripts:
            yield TranscriptEvent(type="partial_transcript", text=partial, language=transcript.language)
        yield TranscriptEvent(
            type="final_transcript",
            text=transcript.text,
            language=transcript.language,
            confidence=transcript.confidence,
            metadata={"backend": "faster_whisper"},
        )

    async def health(self) -> dict[str, object]:
        return {
            "loaded": self.model is not None,
            "status": "ready" if self.model is not None else "unavailable",
            "model": self.model_size,
            "device": self.device,
            "compute_type": self.compute_type,
            "last_error": self.last_error,
            "load_time_ms": self.load_time_ms,
        }

    async def metrics(self) -> dict[str, object]:
        return {
            "voice_backend": "faster_whisper",
            "backend_loaded": self.model is not None,
            "streaming_supported": True,
            "fallback_active": False,
            "model_name": self.model_size,
            "last_error": self.last_error,
            "backend_latency": self.load_time_ms,
        }


FasterWhisperSTTEngine = FasterWhisperBackend
