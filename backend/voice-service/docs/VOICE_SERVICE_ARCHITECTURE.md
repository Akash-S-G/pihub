# IDP Voice Service Architecture

## Scope

`backend/voice-service` is an isolated voice platform for:

- Voice questions
- Voice tutor answers over curriculum RAG
- Lesson narration
- Audio playback
- Streaming TTS
- Pre-generated chapter audio
- STT
- Audio cache and analytics

It does not modify the existing tutor, content pack, curriculum, or RAG services.

## Service Layout

```text
voice-service/
  api/          FastAPI routes and OpenAPI contract
  services/     VoiceGateway, TutorEngine boundary, service errors
  models/       Pydantic request/response/domain models
  cache/        Redis-ready cache abstraction, in-memory implementation
  streaming/    Gemma stream -> TTS chunk -> audio chunk orchestration
  tts/          Svara TTS runtime boundary
  stt/          Distil-Whisper runtime boundary
  audio/        Audio storage and manifest registry
  analytics/    Voice metrics
  tests/        Contract tests with fake engines
```

## API Contract

FastAPI automatically serves:

- `GET /openapi.json`
- `GET /docs`

Endpoints:

- `POST /voice/query`
- `POST /voice/tts`
- `POST /voice/stt`
- `GET /voice/audio/{id}`
- `GET /audio/{asset_id}`
- `GET /voice/metrics`
- `GET /health`

## VoiceGateway Flow

```text
Voice request
  -> pre-generated audio manifest lookup
  -> question/audio cache lookup
  -> curriculum RAG tutor
  -> Svara TTS synthesis
  -> audio storage
  -> cache response
```

## Streaming Flow

```text
Gemma 4 answer stream
  -> text chunks
  -> Svara TTS chunk generation
  -> StreamingResponse audio chunks
```

## Cache Architecture

The `VoiceCache` interface supports:

- question cache
- answer cache
- audio response cache

`InMemoryVoiceCache` is for tests/dev. Production should add a `RedisVoiceCache` implementation behind the same interface.

## Audio Asset Architecture

`AudioStorage` supports filesystem, MinIO, or S3 implementations.

Current implementation:

- `FileSystemAudioStorage`

Audio retrieval supports:

- `Range` requests
- `Accept-Ranges: bytes`
- `ETag`
- browser/client caching

## Audio Manifest Registry

Audio manifests map chapter assets:

```json
{
  "chapter_id": "plants",
  "summary": "plants_summary.wav",
  "concepts": ["photosynthesis.wav"]
}
```

The gateway checks this registry before invoking AI.

## Runtime Boundaries

The architecture defines interfaces for:

- `STTEngine`: Distil-Whisper Large-v3
- `TutorEngine`: Gemma 4 12B over curriculum RAG
- `TTSEngine`: Svara TTS Q3_K_S via llama.cpp

Default concrete classes intentionally return `501` until the runtime/model wiring is configured.

## Analytics

Tracked metrics include:

- `stt_requests`
- `tts_requests`
- `voice_query_requests`
- `audio_cache_hits`
- `audio_cache_misses`
- `streaming_sessions`
- average latency buckets

## Implementation Roadmap

1. Add `RedisVoiceCache`.
2. Add `S3AudioStorage` and `MinIOAudioStorage`.
3. Wire Distil-Whisper Large-v3 runtime.
4. Wire Svara TTS Q3_K_S llama.cpp runtime.
5. Wire Gemma 4 12B tutor to existing curriculum RAG endpoint.
6. Add WebSocket audio streaming if mobile clients require bidirectional sessions.
7. Add Docker Compose service registration after standalone validation.
8. Add load and latency benchmarks for streaming sessions.
