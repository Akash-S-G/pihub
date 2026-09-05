from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any

from analytics import VoiceMetrics
from audio import AudioManifestRegistry, AudioStorage
from cache import VoiceCache
from models import CacheStatus, TTSRequest, TTSResponse, VoiceQueryRequest, VoiceQueryResponse
from services.interfaces import TTSEngine, TutorEngine


class VoiceGateway:
    def __init__(
        self,
        cache: VoiceCache,
        audio_storage: AudioStorage,
        manifests: AudioManifestRegistry,
        tutor: TutorEngine,
        tts: TTSEngine,
        metrics: VoiceMetrics,
    ) -> None:
        self.cache = cache
        self.audio_storage = audio_storage
        self.manifests = manifests
        self.tutor = tutor
        self.tts = tts
        self.metrics = metrics

    async def query(self, request: VoiceQueryRequest) -> VoiceQueryResponse:
        started = time.perf_counter()
        self.metrics.increment("voice_query_requests")

        pre_generated = self.manifests.resolve(request.chapter_id, request.topic, "summary")
        if request.prefer_cached_audio and pre_generated:
            audio = await self.audio_storage.get(pre_generated)
            if audio:
                self.metrics.increment("audio_cache_hits")
                return VoiceQueryResponse(
                    answer_text="",
                    audio_id=pre_generated,
                    audio_url=f"/voice/audio/{pre_generated}",
                    cache_status=CacheStatus.hit,
                    response_source="pre_generated_audio",
                    metrics=self._duration(started),
                )

        key = self._query_key(request)
        cached = await self.cache.get(key)
        if cached:
            self.metrics.increment("audio_cache_hits")
            return _model_validate(VoiceQueryResponse, cached)
        self.metrics.increment("audio_cache_misses")

        filters = {
            "grade": request.grade,
            "subject": request.subject,
            "chapter_id": request.chapter_id,
            "topic": request.topic,
            "language": request.language,
            "require_curriculum_context": request.require_curriculum_context,
        }
        tutor_result = await self.tutor.answer_with_context(request.question or "", filters)
        answer = str(tutor_result.get("answer") or "")
        context = tutor_result.get("context") or []
        audio_result = await self._synthesize_audio(answer, "default", request.language, "wav")
        audio = audio_result["content"]
        audio_id = audio_result.get("audio_id") or f"answer_{hashlib.sha256((key + answer).encode('utf-8')).hexdigest()[:24]}"
        await self.audio_storage.put(audio_id, audio, "audio/wav")
        response = VoiceQueryResponse(
            answer_text=answer,
            audio_id=audio_id,
            audio_url=f"/voice/audio/{audio_id}",
            cache_status=CacheStatus.miss,
            response_source="rag_tutor",
            context_used=context,
            metrics=self._duration(started),
        )
        await self.cache.set(key, _model_dump(response), ttl_seconds=3600)
        return response

    async def tts_only(self, request: TTSRequest) -> TTSResponse:
        self.metrics.increment("tts_requests")
        key = f"tts:{request.language}:{request.voice}:{request.format}:{hashlib.sha256(request.text.encode('utf-8')).hexdigest()}"
        if request.cache:
            cached = await self.cache.get(key)
            if cached:
                self.metrics.increment("audio_cache_hits")
                return _model_copy(_model_validate(TTSResponse, cached), update={"cache_status": CacheStatus.hit})
        self.metrics.increment("audio_cache_misses")
        audio_result = await self._synthesize_audio(request.text, request.voice, request.language, request.format)
        audio = audio_result["content"]
        audio_id = audio_result.get("audio_id") or f"tts_{hashlib.sha256((key + str(len(audio))).encode('utf-8')).hexdigest()[:24]}"
        await self.audio_storage.put(audio_id, audio, f"audio/{request.format}")
        response = TTSResponse(
            audio_id=audio_id,
            audio_url=f"/voice/audio/{audio_id}",
            cache_status=CacheStatus.miss,
            format=request.format,
            duration_ms=audio_result.get("duration_ms"),
        )
        if request.cache:
            await self.cache.set(key, _model_dump(response), ttl_seconds=3600)
        return response

    async def _synthesize_audio(self, text: str, voice: str, language: str, audio_format: str) -> dict[str, Any]:
        if hasattr(self.tts, "synthesize_result"):
            result = await self.tts.synthesize_result(text, voice, language, audio_format)  # type: ignore[attr-defined]
            content = getattr(result, "content", None)
            file_path = getattr(result, "file_path", None)
            if content is None and file_path:
                content = Path(file_path).read_bytes()
            return {
                "content": content,
                "audio_id": result.audio_id,
                "duration_ms": result.duration_ms,
                "sample_rate": result.sample_rate,
                "file_size": getattr(result, "file_size_bytes", getattr(result, "file_size", None)),
            }
        return {"content": await self.tts.synthesize(text, voice, language, audio_format)}

    @staticmethod
    def _query_key(request: VoiceQueryRequest) -> str:
        payload = _model_dump_json(request, exclude_none=True)
        return "voice_query:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _duration(started: float) -> dict[str, Any]:
        return {"voice_response_time_ms": round((time.perf_counter() - started) * 1000, 2)}


def _model_dump(model: Any) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _model_dump_json(model: Any, **kwargs: Any) -> str:
    if hasattr(model, "model_dump_json"):
        return model.model_dump_json(**kwargs)
    return model.json(**kwargs)


def _model_validate(model_cls: Any, data: Any) -> Any:
    if hasattr(model_cls, "model_validate"):
        return model_cls.model_validate(data)
    return model_cls.parse_obj(data)


def _model_copy(model: Any, *, update: dict[str, Any]) -> Any:
    if hasattr(model, "model_copy"):
        return model.model_copy(update=update)
    return model.copy(update=update)
