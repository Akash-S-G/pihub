# Voice Frontend Readiness Report

## Status

PARTIAL FRONTEND READY

The Voice API contract is available through the gateway and nginx at:

```text
/api/voice/*
```

The frontend should never call the internal voice-service paths directly.

Runtime note: the API surface is ready, but real Svara TTS and Distil-Whisper STT depend on mounted models and runtime dependencies. When unavailable, endpoints return structured runtime errors instead of fake success.

## Public Base URL

Use the already discovered backend URL:

```text
ACTIVE_BACKEND_URL
```

All frontend calls should use:

```text
{ACTIVE_BACKEND_URL}/api/voice/...
```

Nginx routes `/api/voice/` to the gateway, and the gateway forwards to the internal `voice-service:8050`.

## Endpoint Summary

| Purpose | Method | Public Endpoint | Body Type | Response |
| --- | --- | --- | --- | --- |
| Voice tutor question | POST | `/api/voice/query` | JSON | JSON |
| Text to speech | POST | `/api/voice/tts` | JSON | JSON or audio stream |
| Speech to text | POST | `/api/voice/stt` | multipart/form-data | JSON |
| Play audio asset | GET | `/api/voice/audio/{asset_id}` | none | audio bytes |
| Voice metrics | GET | `/api/voice/metrics` | none | JSON |
| Backend health | GET | `/health` | none | JSON includes `voice_service` |

## 1. Voice Tutor Question

### Endpoint

```http
POST /api/voice/query
Content-Type: application/json
```

### What To Send

```json
{
  "question": "What is photosynthesis?",
  "student_id": "student_001",
  "grade": 8,
  "subject": "science",
  "chapter_id": "photosynthesis",
  "topic": "photosynthesis",
  "language": "en",
  "stream": false,
  "prefer_cached_audio": true,
  "require_curriculum_context": true
}
```

### Field Notes

| Field | Required | Notes |
| --- | --- | --- |
| `question` | recommended | Text question after STT or typed input. |
| `audio_asset_id` | optional | Reserved for direct asset lookup workflows. |
| `student_id` | optional | For future personalization/analytics. |
| `grade` | optional | Helps tutor/RAG filter curriculum context. |
| `subject` | optional | Example: `maths`, `science`, `social_science`. |
| `chapter_id` | optional | Enables pre-generated audio lookup and RAG filtering. |
| `topic` | optional | Enables concept audio lookup and RAG filtering. |
| `language` | optional | Default `en`; use `hi`, `kn` when needed. |
| `stream` | optional | Currently keep `false` for stable frontend path. |
| `prefer_cached_audio` | optional | If true, service checks pre-generated audio first. |
| `require_curriculum_context` | optional | Keep true so voice tutor does not answer without curriculum context. |

### Success Response

```json
{
  "success": true,
  "answer_text": "Photosynthesis helps plants make food using sunlight...",
  "audio_id": "tts_abc123",
  "audio_url": "/voice/audio/tts_abc123",
  "cache_status": "miss",
  "response_source": "rag_tutor",
  "context_used": [],
  "metrics": {
    "voice_response_time_ms": 1234.5
  }
}
```

### Frontend URL Rule

The service may return:

```text
/voice/audio/{asset_id}
```

The frontend should convert this to the public gateway route:

```text
{ACTIVE_BACKEND_URL}/api/voice/audio/{asset_id}
```

or ignore `audio_url` and build it from `audio_id`.

### Response Sources

| Value | Meaning |
| --- | --- |
| `pre_generated_audio` | Served from curriculum audio manifest. |
| `rag_tutor` | Tutor/RAG generated answer, then TTS audio. |
| `cache` | Reserved cache source. |
| `tts_only` | TTS-only generation path. |

## 2. Text To Speech

### Endpoint

```http
POST /api/voice/tts
Content-Type: application/json
```

### What To Send

```json
{
  "text": "Photosynthesis is the process by which plants make food.",
  "voice": "default",
  "language": "en",
  "stream": false,
  "format": "wav",
  "cache": true
}
```

### Field Notes

| Field | Required | Notes |
| --- | --- | --- |
| `text` | yes | Text to synthesize. |
| `voice` | optional | Current backend maps language internally; `default` is fine. |
| `language` | optional | `en`, `hi`, `kn`; default `en`. |
| `stream` | optional | Use `false` first. Streaming interface exists, runtime streaming is not certified. |
| `format` | optional | `wav`, `mp3`, `ogg`; current runtime path is WAV-first. |
| `cache` | optional | Keep true for repeated playback. |

### Success Response

```json
{
  "success": true,
  "audio_id": "tts_abc123",
  "audio_url": "/voice/audio/tts_abc123",
  "cache_status": "miss",
  "format": "wav",
  "duration_ms": 3200
}
```

### Cache Behavior

First request:

```json
{
  "cache_status": "miss"
}
```

Second identical request:

```json
{
  "cache_status": "hit"
}
```

The cache key is based on:

```text
language + voice + format + sha256(text)
```

## 3. Speech To Text

### Endpoint

```http
POST /api/voice/stt?language=en&enable_partial_transcripts=true
Content-Type: multipart/form-data
```

### What To Send

Multipart form:

```text
file=<recorded wav/m4a/mp3 audio>
```

Query params:

```text
language=en
enable_partial_transcripts=true
```

### Flutter Shape

Send as multipart:

```text
field name: file
filename: recording.wav
content-type: audio/wav
```

### Success Response

```json
{
  "success": true,
  "transcript": "what is photosynthesis",
  "language": "en",
  "partial_transcripts": [
    "what is"
  ],
  "confidence": 0.9,
  "metrics": {}
}
```

### Runtime Note

The STT endpoint contract exists. Real transcription requires the Distil-Whisper runtime to be mounted/configured.

## 4. Audio Playback

### Endpoint

```http
GET /api/voice/audio/{asset_id}
```

### What To Send

No body.

Optional header for seeking/range playback:

```http
Range: bytes=0-1023
```

### Success Headers

```http
HTTP/1.1 200 OK
Content-Type: audio/wav
Content-Length: ...
Accept-Ranges: bytes
Cache-Control: public, max-age=3600
ETag: ...
```

### Range Response

```http
HTTP/1.1 206 Partial Content
Content-Range: bytes 0-1023/123456
Accept-Ranges: bytes
```

### Frontend Playback Flow

1. Receive `audio_id` from `/api/voice/query` or `/api/voice/tts`.
2. Build:

```text
{ACTIVE_BACKEND_URL}/api/voice/audio/{audio_id}
```

3. Give that URL to the audio player.
4. Support normal HTTP range playback.

## 5. Metrics

### Endpoint

```http
GET /api/voice/metrics
```

### Response Example

```json
{
  "voice_query_requests": 1,
  "tts_requests": 2,
  "stt_requests": 1,
  "audio_cache_hits": 1,
  "audio_cache_misses": 2
}
```

This is mostly for diagnostics screens and backend logs.

## 6. Health And Discovery

### Health

```http
GET /health
```

Expected gateway shape includes:

```json
{
  "voice_service": {
    "healthy": true
  }
}
```

Voice-service health includes TTS detail:

```json
{
  "voice_service": {
    "tts": {
      "provider": "svara_local",
      "gguf_loaded": true,
      "snac_loaded": true,
      "status": "ready"
    }
  }
}
```

### Discovery

Gateway discovery advertises voice support:

```json
{
  "supports_voice": true
}
```

Frontend should still gate voice UI on health/runtime readiness, not only discovery.

## Error Contract

Runtime errors use:

```json
{
  "detail": {
    "success": false,
    "error": {
      "code": "VOICE_RUNTIME_UNAVAILABLE",
      "message": "Svara GGUF not found: ..."
    }
  }
}
```

Common codes:

| Code | Meaning |
| --- | --- |
| `VOICE_RUNTIME_DISABLED` | TTS disabled by config. |
| `VOICE_RUNTIME_UNAVAILABLE` | Model/decoder missing or unavailable. |
| `VOICE_RUNTIME_DEPENDENCY_MISSING` | Python/native runtime dependency missing. |
| `VOICE_RUNTIME_LOAD_FAILED` | Model or decoder failed to load. |
| `VOICE_TTS_EMPTY_TEXT` | Empty TTS input. |
| `VOICE_TTS_GENERATION_FAILED` | Runtime failed during synthesis. |
| `AUDIO_NOT_FOUND` | Requested audio asset does not exist. |

## Recommended Frontend Workflows

### A. Voice Question

```text
Record audio
-> POST /api/voice/stt
-> show transcript
-> POST /api/voice/query with transcript + curriculum filters
-> display answer_text
-> play /api/voice/audio/{audio_id}
```

### B. Typed Question With Voice Answer

```text
User types question
-> POST /api/voice/query
-> display answer_text
-> play audio_id
```

### C. Lesson Narration / Read Aloud

```text
Text selected from chapter
-> POST /api/voice/tts
-> play /api/voice/audio/{audio_id}
```

### D. Pre-Generated Chapter Audio

```text
POST /api/voice/query
{
  "chapter_id": "...",
  "topic": "...",
  "prefer_cached_audio": true
}
```

If a matching manifest entry exists, response source is:

```text
pre_generated_audio
```

## Flutter DTOs

### VoiceQueryRequest

```dart
class VoiceQueryRequest {
  final String? question;
  final String? studentId;
  final int? grade;
  final String? subject;
  final String? chapterId;
  final String? topic;
  final String language;
  final bool stream;
  final bool preferCachedAudio;
  final bool requireCurriculumContext;
}
```

### VoiceQueryResponse

```dart
class VoiceQueryResponse {
  final bool success;
  final String answerText;
  final String? audioId;
  final String? audioUrl;
  final String cacheStatus;
  final String responseSource;
  final List<Map<String, dynamic>> contextUsed;
  final Map<String, dynamic> metrics;
}
```

### TTSRequest

```dart
class TtsRequest {
  final String text;
  final String voice;
  final String language;
  final bool stream;
  final String format;
  final bool cache;
}
```

### TTSResponse

```dart
class TtsResponse {
  final bool success;
  final String audioId;
  final String audioUrl;
  final String cacheStatus;
  final String format;
  final int? durationMs;
}
```

### STTResponse

```dart
class SttResponse {
  final bool success;
  final String transcript;
  final String language;
  final List<String> partialTranscripts;
  final double? confidence;
  final Map<String, dynamic> metrics;
}
```

## Frontend Implementation Notes

1. Always call gateway paths, not internal service paths.

```text
GOOD: /api/voice/tts
BAD:  /voice/tts
```

2. Normalize returned audio URLs.

If backend returns:

```text
/voice/audio/tts_abc
```

convert to:

```text
/api/voice/audio/tts_abc
```

3. Treat voice runtime as optional.

Show voice UI only when:

```text
/health says voice_service.healthy == true
and TTS/STT runtime checks are ready if required
```

4. Keep `require_curriculum_context=true` for tutor questions.

5. Use `stream=false` until streaming runtime is certified end-to-end.

6. Use `format="wav"` for first integration.

## Readiness Matrix

| Area | Status | Notes |
| --- | --- | --- |
| Gateway routes | READY | `/api/voice/*` exists. |
| Nginx routing | READY | `/api/voice/` proxies to gateway with buffering off. |
| JSON contracts | READY | Pydantic DTOs exist. |
| Audio byte serving | READY | Supports `GET`, `Range`, `ETag`, `Content-Length`. |
| TTS cache | READY | Miss then hit behavior verified. |
| Voice query path | PARTIAL | Contract ready; depends on tutor + TTS runtime availability. |
| STT | PARTIAL | Contract ready; Distil-Whisper runtime pending/config-dependent. |
| Svara TTS | PARTIAL | Local provider implemented; real WAV certification pending in clean runtime. |
| Streaming TTS | NOT READY | Interface exists; runtime streaming not implemented. |
| Pre-generated audio | READY FOUNDATION | Manifest resolver exists; requires audio manifest/assets. |

## Final Frontend Guidance

Start frontend integration with this order:

1. Health check display.
2. `/api/voice/tts` with typed text, `stream=false`, `format=wav`.
3. Audio playback via `/api/voice/audio/{audio_id}`.
4. `/api/voice/stt` upload flow.
5. `/api/voice/query` voice tutor flow.
6. Streaming only after non-streaming TTS is certified.

