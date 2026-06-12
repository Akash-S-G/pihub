from __future__ import annotations

import os
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from analytics import VoiceMetrics
from api import router
from audio import AudioManifestRegistry, FileSystemAudioStorage
from cache import InMemoryVoiceCache
from services.tutor_engine import RagTutorEngine
from services.voice_gateway import VoiceGateway
from stt import DistilWhisperSTTEngine
from streaming import VoiceStreamer
from tts import SvaraTTSEngine


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        tts_engine = getattr(app.state, "tts_engine", None)
        if hasattr(tts_engine, "warmup"):
            await tts_engine.warmup()
        try:
            yield
        finally:
            tts_engine = getattr(app.state, "tts_engine", None)
            if hasattr(tts_engine, "close"):
                await tts_engine.close()

    app = FastAPI(
        title="IDP Voice Service",
        version="1.0.0",
        description="Voice questions, voice tutor, STT, TTS, pre-generated audio, streaming audio, and analytics.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    audio_root = Path(os.getenv("VOICE_AUDIO_ROOT", "/tmp/idp_voice_audio"))
    manifest_path = os.getenv("VOICE_AUDIO_MANIFEST", "")
    metrics = VoiceMetrics()
    cache = InMemoryVoiceCache()
    storage = FileSystemAudioStorage(audio_root)
    manifests = AudioManifestRegistry(manifest_path or None)
    tutor = RagTutorEngine()
    tts = SvaraTTSEngine()
    stt = DistilWhisperSTTEngine()

    app.state.voice_metrics = metrics
    app.state.voice_cache = cache
    app.state.audio_storage = storage
    app.state.audio_manifest_registry = manifests
    app.state.tutor_engine = tutor
    app.state.tts_engine = tts
    app.state.stt_engine = stt
    app.state.voice_gateway = VoiceGateway(cache, storage, manifests, tutor, tts, metrics)
    app.state.voice_streamer = VoiceStreamer(tutor, tts)

    app.include_router(router)
    return app


app = create_app()


@app.get("/health", tags=["health"])
async def health() -> dict[str, object]:
    tts_health: dict[str, Any] = {"loaded": False, "status": "unknown"}
    tts_engine = getattr(app.state, "tts_engine", None)
    if hasattr(tts_engine, "health_check"):
        tts_health = await tts_engine.health_check()

    return {
        "status": "healthy",
        "service": "voice-service",
        "voice_service": {
            "tts": tts_health,
        },
        "capabilities": {
            "voice_query": True,
            "stt": True,
            "tts": True,
            "streaming_tts": True,
            "pre_generated_audio": True,
            "range_requests": True,
        },
    }
