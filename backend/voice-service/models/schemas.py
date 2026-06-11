from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class CacheStatus(str, Enum):
    hit = "hit"
    miss = "miss"
    bypassed = "bypassed"


class VoiceQueryRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    question: str | None = None
    audio_asset_id: str | None = None
    student_id: str | None = None
    grade: int | None = None
    subject: str | None = None
    chapter_id: str | None = None
    topic: str | None = None
    language: str = "en"
    stream: bool = False
    prefer_cached_audio: bool = True
    require_curriculum_context: bool = True


class VoiceQueryResponse(BaseModel):
    success: bool = True
    answer_text: str
    audio_id: str | None = None
    audio_url: str | None = None
    cache_status: CacheStatus
    response_source: Literal["pre_generated_audio", "cache", "rag_tutor", "tts_only"]
    context_used: list[dict[str, Any]] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)


class TTSRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    text: str
    voice: str = "default"
    language: str = "en"
    stream: bool = False
    format: Literal["wav", "mp3", "ogg"] = "wav"
    cache: bool = True


class TTSResponse(BaseModel):
    success: bool = True
    audio_id: str
    audio_url: str
    cache_status: CacheStatus
    format: str = "wav"
    duration_ms: int | None = None


class STTRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    language: str | None = None
    enable_partial_transcripts: bool = False


class STTResponse(BaseModel):
    success: bool = True
    transcript: str
    language: str
    partial_transcripts: list[str] = Field(default_factory=list)
    confidence: float | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)


class AudioAsset(BaseModel):
    asset_id: str
    path: str
    content_type: str = "audio/wav"
    size_bytes: int = 0
    checksum: str | None = None
    chapter_id: str | None = None
    kind: Literal["summary", "glossary", "concept", "answer", "lesson", "other"] = "other"
    metadata: dict[str, Any] = Field(default_factory=dict)


class AudioManifest(BaseModel):
    chapter_id: str
    summary: str | None = None
    concepts: list[str] = Field(default_factory=list)
    glossary: str | None = None
    lesson: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
