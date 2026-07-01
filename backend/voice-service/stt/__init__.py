from __future__ import annotations

import os

from .base import STTEngine, Transcript, TranscriptEvent, VoiceBackend
from .faster_whisper import FasterWhisperBackend, FasterWhisperSTTEngine
from .gemma4_audio import Gemma4AudioBackend, Gemma4AudioSTTEngine
from .manager import VoiceBackendManager
from .mock import MockSTTEngine
from .distil_whisper import DistilWhisperSTTEngine


def get_stt_engine() -> VoiceBackend:
    voice_backend = os.getenv("VOICE_BACKEND", os.getenv("STT_PROVIDER", "faster_whisper")).strip().lower()
    if voice_backend in {"gemma4_audio", "gemma", "gemma_audio"}:
        primary: VoiceBackend = Gemma4AudioBackend()
        fallback: VoiceBackend = FasterWhisperBackend()
        return VoiceBackendManager(primary, fallback, primary_name="gemma4_audio", fallback_name="faster_whisper")
    if voice_backend in {"faster_whisper", "whisper", "faster-whisper"}:
        return FasterWhisperBackend()
    if voice_backend in {"distil-whisper", "distil_whisper"}:
        return DistilWhisperSTTEngine()
    return MockSTTEngine()


__all__ = [
    "STTEngine",
    "VoiceBackend",
    "Transcript",
    "TranscriptEvent",
    "MockSTTEngine",
    "DistilWhisperSTTEngine",
    "FasterWhisperBackend",
    "FasterWhisperSTTEngine",
    "Gemma4AudioBackend",
    "Gemma4AudioSTTEngine",
    "VoiceBackendManager",
    "get_stt_engine",
]
