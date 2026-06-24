from __future__ import annotations

import os
import time
import tempfile
import logging
import asyncio
from .base import STTEngine, Transcript

logger = logging.getLogger(__name__)

class FasterWhisperSTTEngine(STTEngine):
    _model_instance = None

    def __init__(self) -> None:
        self.model_size = os.getenv("WHISPER_MODEL", "small")
        self.device = os.getenv("WHISPER_DEVICE", "cpu")
        self.compute_type = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
        self._load_model()

    def _load_model(self):
        if FasterWhisperSTTEngine._model_instance is None:
            try:
                from faster_whisper import WhisperModel
                logger.info(f"Loading Faster Whisper model '{self.model_size}' on {self.device} with compute type {self.compute_type}")
                FasterWhisperSTTEngine._model_instance = WhisperModel(
                    self.model_size, 
                    device=self.device, 
                    compute_type=self.compute_type,
                    download_root="/models"
                )
                logger.info("Faster Whisper model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load Faster Whisper model: {e}")
                raise

    @property
    def model(self):
        return FasterWhisperSTTEngine._model_instance

    async def transcribe(self, audio: bytes, language: str | None = None) -> Transcript:
        start_time = time.perf_counter()
        
        # faster-whisper needs a file-like object or a path
        # Write bytes to a temporary file
        def run_transcribe():
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
                tmp.write(audio)
                tmp.flush()
                
                kwargs = {}
                if language:
                    kwargs["language"] = language
                    
                segments, info = self.model.transcribe(tmp.name, beam_size=5, **kwargs)
                
                # force evaluation of generator to get all text before file closes
                text = " ".join([segment.text for segment in segments]).strip()
                return text, info
        
        loop = asyncio.get_running_loop()
        text, info = await loop.run_in_executor(None, run_transcribe)

        latency_ms = (time.perf_counter() - start_time) * 1000
        
        return Transcript(
            text=text,
            language=info.language,
            confidence=info.language_probability,
            latency_ms=latency_ms
        )
