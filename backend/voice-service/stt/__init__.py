from __future__ import annotations

import os
from .base import STTEngine
from .mock import MockSTTEngine
from .distil_whisper import DistilWhisperSTTEngine
from .faster_whisper import FasterWhisperSTTEngine

def get_stt_engine() -> STTEngine:
    provider = os.getenv("STT_PROVIDER", "mock").lower()
    if provider == "distil-whisper" or provider == "whisper":
        return DistilWhisperSTTEngine()
    elif provider == "faster_whisper":
        return FasterWhisperSTTEngine()
    return MockSTTEngine()

__all__ = ["STTEngine", "MockSTTEngine", "DistilWhisperSTTEngine", "FasterWhisperSTTEngine", "get_stt_engine"]
