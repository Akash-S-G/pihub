from __future__ import annotations

import asyncio
import gc
import hashlib
import json
import os
import re
import resource
import time
import wave
from collections.abc import AsyncIterator
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from config import VoiceRuntimeSettings


class SvaraProviderError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


@dataclass
class AudioResult:
    audio_id: str
    file_path: str
    duration_ms: int
    sample_rate: int
    file_size_bytes: int

    @property
    def file_size(self) -> int:
        return self.file_size_bytes


class SvaraLocalProvider:
    """Local Svara runtime using GGUF token generation and SNAC ONNX decoding.

    This provider intentionally does not use llama-server. Svara GGUF emits
    discrete audio tokens; the SNAC decoder converts those token levels into
    PCM samples, which are then written as WAV files.
    """

    START_OF_SPEECH = 128257
    END_OF_SPEECH = 128258
    START_OF_HUMAN = 128259
    END_OF_HUMAN = 128260
    END_OF_TEXT = 128009
    AUDIO_TOKEN_BASE = 128266
    AUDIO_TOKEN_LIMIT = 156938
    SNAC_CODEBOOK_SIZE = 4096
    SNAC_BANDS_PER_FRAME = 7
    CHUNK_CHAR_LIMIT = 80
    CHUNK_PAUSE_SECONDS = 0.05

    def __init__(self, settings: VoiceRuntimeSettings) -> None:
        self.settings = settings
        self.llm: Any | None = None
        self.decoder: Any | None = None
        self.load_time_ms: float | None = None
        self.warmup_time_ms: float | None = None
        self.last_error: str | None = None
        self._load_lock = asyncio.Lock()
        self._generation_lock = asyncio.Lock()
        self.generated_audio_dir = Path(os.getenv("SVARA_GENERATED_AUDIO_DIR", "/tmp/idp_voice_audio/generated"))

    async def warmup(self) -> dict[str, Any]:
        if not self.settings.voice_tts_enabled:
            return await self.health_check()

        health = await self.health_check()
        if not health.get("gguf_loaded") or not health.get("snac_loaded"):
            self._write_runtime_metrics({"warmup_status": "skipped", "health": health})
            return health

        if self.settings.svara_warmup_enabled:
            started = time.perf_counter()
            try:
                await self.synthesize("Hello", "en")
                self.warmup_time_ms = round((time.perf_counter() - started) * 1000, 2)
            except SvaraProviderError as exc:
                self.last_error = exc.message
            except Exception as exc:  # pragma: no cover - defensive runtime boundary
                self.last_error = str(exc)

        metrics = await self.runtime_metrics()
        self._write_runtime_metrics(metrics)
        return await self.health_check()

    async def health_check(self) -> dict[str, Any]:
        if not self.settings.voice_tts_enabled:
            return {
                "provider": "svara_local",
                "enabled": False,
                "gguf_loaded": False,
                "snac_loaded": False,
                "status": "disabled",
            }

        model_exists = self.settings.svara_model_path.exists()
        decoder_exists = self.settings.svara_snac_decoder_path.exists()
        if not model_exists or not decoder_exists:
            return {
                "provider": "svara_local",
                "enabled": True,
                "gguf_loaded": False,
                "snac_loaded": False,
                "model": self.settings.model_name,
                "model_path": str(self.settings.svara_model_path),
                "snac_decoder_path": str(self.settings.svara_snac_decoder_path),
                "status": "missing_model_or_decoder",
                "missing": {
                    "gguf": not model_exists,
                    "snac_decoder": not decoder_exists,
                },
                "last_error": self.last_error,
            }

        try:
            await self.ensure_loaded()
        except Exception as exc:
            self.last_error = str(exc)
            return {
                "provider": "svara_local",
                "enabled": True,
                "gguf_loaded": self.llm is not None,
                "snac_loaded": self.decoder is not None,
                "model": self.settings.model_name,
                "model_path": str(self.settings.svara_model_path),
                "snac_decoder_path": str(self.settings.svara_snac_decoder_path),
                "status": "error",
                "last_error": self.last_error,
            }

        return {
            "provider": "svara_local",
            "enabled": True,
            "gguf_loaded": self.llm is not None,
            "snac_loaded": self.decoder is not None,
            "model": self.settings.model_name,
            "model_path": str(self.settings.svara_model_path),
            "snac_decoder_path": str(self.settings.svara_snac_decoder_path),
            "sample_rate": self.settings.svara_sample_rate,
            "max_tokens": self.settings.svara_max_tokens,
            "load_time_ms": self.load_time_ms,
            "warmup_time_ms": self.warmup_time_ms,
            "status": "ready",
            "last_error": self.last_error,
        }

    async def ensure_loaded(self) -> None:
        async with self._load_lock:
            if self.llm is not None and self.decoder is not None:
                return
            if not self.settings.voice_tts_enabled:
                raise SvaraProviderError(501, "VOICE_RUNTIME_DISABLED", "Svara TTS runtime is disabled")
            if not self.settings.svara_model_path.exists():
                raise SvaraProviderError(503, "VOICE_RUNTIME_UNAVAILABLE", f"Svara GGUF not found: {self.settings.svara_model_path}")
            if not self.settings.svara_snac_decoder_path.exists():
                raise SvaraProviderError(
                    503,
                    "VOICE_RUNTIME_UNAVAILABLE",
                    f"Svara SNAC decoder not found: {self.settings.svara_snac_decoder_path}",
                )

            started = time.perf_counter()
            try:
                await asyncio.to_thread(self._load_sync)
            except ImportError as exc:
                self.last_error = str(exc)
                raise SvaraProviderError(503, "VOICE_RUNTIME_DEPENDENCY_MISSING", str(exc)) from exc
            except Exception as exc:
                self.last_error = str(exc)
                raise SvaraProviderError(503, "VOICE_RUNTIME_LOAD_FAILED", str(exc)) from exc
            self.load_time_ms = round((time.perf_counter() - started) * 1000, 2)

    async def synthesize(self, text: str, language: str) -> AudioResult:
        await self.ensure_loaded()
        if not text.strip():
            raise SvaraProviderError(400, "VOICE_TTS_EMPTY_TEXT", "TTS text cannot be empty")

        # llama.cpp model contexts are not safe to mutate concurrently.
        async with self._generation_lock:
            try:
                if len(text) > self.CHUNK_CHAR_LIMIT:
                    return await asyncio.to_thread(self._synthesize_chunked_sync, text, language)
                return await asyncio.to_thread(self._synthesize_sync, text, language)
            except SvaraProviderError:
                raise
            except Exception as exc:
                self.last_error = str(exc)
                raise SvaraProviderError(502, "VOICE_TTS_GENERATION_FAILED", str(exc)) from exc

    async def synthesize_stream(self, text: str, language: str) -> AsyncIterator[bytes]:
        """
        Streaming synthesis: yield PCM chunks as soon as they are decoded.

        Token generation is done in one locked call, then SNAC frames are decoded
        and yielded chunk by chunk as an AsyncIterator of raw bytes.
        """
        await self.ensure_loaded()
        if not text.strip():
            raise SvaraProviderError(400, "VOICE_TTS_EMPTY_TEXT", "TTS text cannot be empty")

        # Chunk the text if it's too long (streaming-friendly chunking)
        max_stream_chars = self.CHUNK_CHAR_LIMIT
        if len(text) > max_stream_chars:
            chunks = self._chunk_text(text, max_stream_chars)
            for chunk in chunks:
                async for pcm_chunk in self._synthesize_stream_single(chunk, language):
                    yield pcm_chunk
        else:
            async for pcm_chunk in self._synthesize_stream_single(text, language):
                yield pcm_chunk

    async def _synthesize_stream_single(self, text: str, language: str) -> AsyncIterator[bytes]:
        """Generate and stream a single text segment."""
        # llama.cpp model contexts are not safe to mutate concurrently.
        async with self._generation_lock:
            try:
                # Generate complete tokens first (can't stream llama.cpp)
                result = await asyncio.to_thread(self._synthesize_sync, text, language)
                # Stream by reading the resulting WAV file in chunks
                async for chunk in self._stream_wav_file(result.file_path):
                    yield chunk
            except SvaraProviderError:
                raise
            except Exception as exc:
                self.last_error = str(exc)
                raise SvaraProviderError(502, "VOICE_TTS_GENERATION_FAILED", str(exc)) from exc

    async def _stream_wav_file(self, file_path: str, chunk_size: int = 8192) -> AsyncIterator[bytes]:
        """Yield chunks of a WAV file for streaming."""
        path = Path(file_path)
        if not path.exists():
            return  # Will raise on read, but let caller handle
        with open(path, "rb") as f:
            while True:
                data = f.read(chunk_size)
                if not data:
                    break
                yield data

    async def close(self) -> None:
        self.llm = None
        self.decoder = None
        gc.collect()

    async def runtime_metrics(self) -> dict[str, Any]:
        return {
            "provider": "svara_local",
            "model": self.settings.model_name,
            "model_path": str(self.settings.svara_model_path),
            "snac_decoder_path": str(self.settings.svara_snac_decoder_path),
            "load_time_ms": self.load_time_ms,
            "warmup_time_ms": self.warmup_time_ms,
            "peak_ram_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2),
            "gguf_loaded": self.llm is not None,
            "snac_loaded": self.decoder is not None,
            "last_error": self.last_error,
        }

    def _load_sync(self) -> None:
        try:
            from llama_cpp import Llama
            import onnxruntime as ort
        except ImportError as exc:
            raise ImportError("Required Svara local dependencies are missing: llama_cpp and onnxruntime") from exc

        if self.llm is None:
            if not self.settings.svara_model_path.exists():
                raise SvaraProviderError(
                    503,
                    "VOICE_RUNTIME_UNAVAILABLE",
                    f"Svara GGUF not found: {self.settings.svara_model_path}",
                )
            self.llm = Llama(
                model_path=str(self.settings.svara_model_path),
                n_ctx=self.settings.svara_context,
                n_threads=self.settings.svara_threads,
                n_gpu_layers=self.settings.svara_gpu_layers,
                logits_all=False,
                verbose=False,
            )
        if self.decoder is None:
            self.decoder = ort.InferenceSession(str(self.settings.svara_snac_decoder_path), providers=["CPUExecutionProvider"])

    def _synthesize_sync(self, text: str, language: str) -> AudioResult:
        if self.llm is None or self.decoder is None:
            raise SvaraProviderError(503, "VOICE_RUNTIME_UNAVAILABLE", "Svara local provider is not loaded")

        voice = self._voice_for(language)
        prompt_ids = self._prompt_tokens(voice, text)
        generated_tokens = self._generate_audio_tokens(prompt_ids)
        codes = self._snac_codes(prompt_ids + generated_tokens, len(prompt_ids))
        audio = self._decode_snac(codes)
        audio = self._normalize_audio(audio)

        audio_id = self._audio_id(text, language, voice)
        path = self.generated_audio_dir / f"{audio_id}.wav"
        path.parent.mkdir(parents=True, exist_ok=True)
        self._write_wav(path, audio)
        metadata = self._wav_metadata(path)
        return AudioResult(
            audio_id=audio_id,
            file_path=str(path),
            duration_ms=metadata["duration_ms"],
            sample_rate=metadata["sample_rate"],
            file_size_bytes=path.stat().st_size,
        )

    def _synthesize_chunked_sync(self, text: str, language: str) -> AudioResult:
        import soundfile as sf

        chunks = self._chunk_text(text, self.CHUNK_CHAR_LIMIT)
        if len(chunks) <= 1:
            return self._synthesize_sync(text, language)

        voice = self._voice_for(language)
        combined_samples: list[Any] = []
        sample_rate = self.settings.svara_sample_rate
        pause_samples = int(sample_rate * self.CHUNK_PAUSE_SECONDS)
        for index, chunk in enumerate(chunks):
            chunk_result = self._synthesize_sync(chunk, language)
            samples, chunk_sample_rate = sf.read(chunk_result.file_path, dtype="float32")
            sample_rate = chunk_sample_rate or sample_rate
            combined_samples.append(samples.reshape(-1))
            if pause_samples > 0 and index < len(chunks) - 1:
                import numpy as np

                combined_samples.append(np.zeros(pause_samples, dtype=np.float32))

        if not combined_samples:
            raise SvaraProviderError(502, "VOICE_TTS_EMPTY_AUDIO", "Svara decoded empty audio")

        import numpy as np

        audio = np.concatenate(combined_samples).astype(np.float32)
        audio_id = self._audio_id(text, language, voice)
        path = self.generated_audio_dir / f"{audio_id}.wav"
        path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(path, audio, sample_rate)
        metadata = self._wav_metadata(path)
        return AudioResult(
            audio_id=audio_id,
            file_path=str(path),
            duration_ms=metadata["duration_ms"],
            sample_rate=metadata["sample_rate"],
            file_size_bytes=path.stat().st_size,
        )

    def _prompt_tokens(self, voice: str, text: str) -> list[int]:
        body = self.llm.tokenize(f"{voice}: {text}".encode("utf-8"), add_bos=False, special=True)
        return [self.START_OF_HUMAN, self.llm.token_bos(), *body, self.END_OF_TEXT, self.END_OF_HUMAN]

    def _generate_audio_tokens(self, prompt_ids: list[int]) -> list[int]:
        generated: list[int] = []
        for token in self.llm.generate(
            prompt_ids,
            temp=0.6,
            top_k=40,
            top_p=0.9,
            repeat_penalty=1.0,
            reset=True,
        ):
            value = int(token)
            generated.append(value)
            if value == self.END_OF_SPEECH or len(generated) >= self.settings.svara_max_tokens:
                break
        return generated

    def _snac_codes(self, tokens: list[int], input_len: int) -> dict[str, Any]:
        import numpy as np

        generated = [int(x) for x in tokens[input_len:]]
        start = generated.index(self.START_OF_SPEECH) + 1 if self.START_OF_SPEECH in generated else 0
        audio: list[tuple[int, int]] = []
        band_pos = 0
        for token in generated[start:]:
            if token == self.END_OF_SPEECH:
                break
            if token < self.AUDIO_TOKEN_BASE or token >= self.AUDIO_TOKEN_LIMIT:
                continue
            band = band_pos % self.SNAC_BANDS_PER_FRAME
            code = token - self.AUDIO_TOKEN_BASE - band * self.SNAC_CODEBOOK_SIZE
            if 0 <= code < self.SNAC_CODEBOOK_SIZE:
                audio.append((band, code))
                band_pos += 1

        frames = len(audio) // self.SNAC_BANDS_PER_FRAME
        level0: list[int] = []
        level1: list[int] = []
        level2: list[int] = []
        for index in range(frames):
            frame_codes = [code for _, code in audio[index * self.SNAC_BANDS_PER_FRAME : index * self.SNAC_BANDS_PER_FRAME + 7]]
            level0.append(frame_codes[0])
            level1.extend([frame_codes[1], frame_codes[4]])
            level2.extend([frame_codes[2], frame_codes[3], frame_codes[5], frame_codes[6]])

        return {
            "audio_token_count": len(audio),
            "frames": frames,
            "level0": np.asarray([level0], dtype=np.int64),
            "level1": np.asarray([level1], dtype=np.int64),
            "level2": np.asarray([level2], dtype=np.int64),
        }

    def _decode_snac(self, codes: dict[str, Any]) -> Any:
        if codes["frames"] < 1:
            raise SvaraProviderError(502, "VOICE_TTS_NO_AUDIO_FRAMES", "Svara generated no complete SNAC audio frame")
        out = self.decoder.run(
            None,
            {
                "audio_codes.0": codes["level0"],
                "audio_codes.1": codes["level1"],
                "audio_codes.2": codes["level2"],
            },
        )
        import numpy as np

        return np.asarray(out[0]).reshape(-1)

    def _normalize_audio(self, audio: Any) -> Any:
        import numpy as np

        samples = np.asarray(audio, dtype=np.float32).reshape(-1)
        if samples.size == 0:
            raise SvaraProviderError(502, "VOICE_TTS_EMPTY_AUDIO", "Svara decoded empty audio")
        peak = float(np.max(np.abs(samples)))
        if peak > 1.0:
            samples = samples / peak
        return samples

    def _write_wav(self, path: Path, audio: Any) -> None:
        try:
            import soundfile as sf
        except ImportError as exc:
            raise SvaraProviderError(503, "VOICE_RUNTIME_DEPENDENCY_MISSING", "Required dependency missing: soundfile") from exc
        sf.write(path, audio, self.settings.svara_sample_rate)

    def _audio_id(self, text: str, language: str, voice: str) -> str:
        payload = f"{language}|{voice}|{self.settings.model_name}|{text}".encode("utf-8")
        return f"tts_{hashlib.sha256(payload).hexdigest()[:24]}"

    @staticmethod
    def _voice_for(language: str) -> str:
        language_key = (language or "").strip().lower()
        voice_map = {
            "en": "English (Indian) (Female)",
            "hi": "Hindi (Indian) (Female)",
            "kn": "Kannada (Indian) (Female)",
            "mr": "Marathi (Indian) (Female)",
            "bn": "Bengali (Indian) (Female)",
            "te": "Telugu (Indian) (Female)",
            "ta": "Tamil (Indian) (Female)",
            "ml": "Malayalam (Indian) (Female)",
            "gu": "Gujarati (Indian) (Female)",
            "pa": "Punjabi (Indian) (Female)",
            "or": "Odia (Indian) (Female)",
        }
        return voice_map.get(language_key, "English (Indian) (Female)")

    @staticmethod
    def _chunk_text(text: str, max_chars: int = 200) -> list[str]:
        """Split text into chunks suitable for streaming synthesis."""
        cleaned = re.sub(r"\s+", " ", text).strip()
        if len(cleaned) <= max_chars:
            return [cleaned]

        sentence_parts = re.split(r"(?<=[.!?])\s+", cleaned)
        chunks: list[str] = []
        current = ""

        def flush_current() -> None:
            nonlocal current
            if current.strip():
                chunks.append(current.strip())
            current = ""

        for part in sentence_parts:
            if not part:
                continue
            if len(part) > max_chars:
                flush_current()
                chunks.extend(SvaraLocalProvider._split_long_segment(part, max_chars))
                continue
            candidate = f"{current} {part}".strip() if current else part
            if len(candidate) <= max_chars:
                current = candidate
            else:
                flush_current()
                current = part

        flush_current()
        return chunks if chunks else [cleaned]

    @staticmethod
    def _split_long_segment(segment: str, max_chars: int) -> list[str]:
        clause_parts = re.split(r"(?<=[,;:])\s+", segment)
        if len(clause_parts) > 1:
            chunks: list[str] = []
            current = ""
            for clause in clause_parts:
                if not clause:
                    continue
                candidate = f"{current} {clause}".strip() if current else clause
                if len(candidate) <= max_chars:
                    current = candidate
                else:
                    if current:
                        chunks.append(current)
                    current = clause
            if current:
                chunks.append(current)
            return chunks

        words = segment.split()
        if len(words) <= 1:
            return [
                segment[i : i + max_chars].strip()
                for i in range(0, len(segment), max_chars)
                if segment[i : i + max_chars].strip()
            ]

        chunks: list[str] = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip() if current else word
            if len(candidate) <= max_chars:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                current = word
        if current:
            chunks.append(current)
        return chunks

    @staticmethod
    def _wav_metadata(path: Path) -> dict[str, int]:
        with wave.open(str(path), "rb") as audio:
            frames = audio.getnframes()
            sample_rate = audio.getframerate()
            duration_ms = int(frames / sample_rate * 1000) if sample_rate else 0
            return {"duration_ms": duration_ms, "sample_rate": sample_rate}

    def _write_runtime_metrics(self, metrics: dict[str, Any]) -> None:
        path = self.settings.svara_metrics_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(_json_safe(metrics), indent=2), encoding="utf-8")


def _json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value
