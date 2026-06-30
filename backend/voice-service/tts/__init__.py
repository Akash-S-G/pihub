from __future__ import annotations

import os
from config import get_runtime_settings
from .base import TTSEngine
from .mock import MockTTSEngine
from .svara_tts import SvaraTTSEngine
from .providers import AudioResult, SvaraLocalProvider

def get_tts_engine() -> TTSEngine:
    provider = os.getenv("TTS_PROVIDER", "auto").lower()
    if provider == "svara":
        return SvaraTTSEngine()
    if provider not in {"auto", "mock"}:
        return MockTTSEngine()

    runtime = get_runtime_settings()
    model_available = runtime.svara_model_path.exists()
    if runtime.voice_tts_enabled and model_available and runtime.svara_snac_decoder_path.exists():
        return SvaraTTSEngine()
    return MockTTSEngine()

__all__ = ["TTSEngine", "MockTTSEngine", "SvaraTTSEngine", "AudioResult", "SvaraLocalProvider", "get_tts_engine"]
