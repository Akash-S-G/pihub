from __future__ import annotations

import os
from .base import TTSEngine
from .mock import MockTTSEngine
from .svara_tts import SvaraTTSEngine
from .providers import AudioResult, SvaraLocalProvider

def get_tts_engine() -> TTSEngine:
    provider = os.getenv("TTS_PROVIDER", "mock").lower()
    if provider == "svara":
        return SvaraTTSEngine()
    return MockTTSEngine()

__all__ = ["TTSEngine", "MockTTSEngine", "SvaraTTSEngine", "AudioResult", "SvaraLocalProvider", "get_tts_engine"]
