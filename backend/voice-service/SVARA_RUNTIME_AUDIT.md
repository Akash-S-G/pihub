# Svara Runtime Audit

Generated: 2026-06-11

## Scope

Audited:

```text
backend/voice-service/
backend/inference-service/
```

Goal: reuse existing runtime patterns where possible and avoid duplicating tutor/RAG logic.

## Existing Voice Service Runtime State

The voice service already had:

- `TTSEngine` abstraction in `services/interfaces.py`
- `SvaraTTSEngine` boundary in `tts/svara_tts.py`
- `VoiceGateway` cache and audio storage flow in `services/voice_gateway.py`
- Filesystem audio storage in `audio/storage.py`
- Health endpoint in `app.py`

Before this sprint:

```text
SvaraTTSEngine.synthesize()
-> 501 VOICE_RUNTIME_NOT_CONFIGURED
```

## Existing llama.cpp Infrastructure

`backend/inference-service/app/main.py` contains the reusable runtime pattern:

- Persistent `llama-server` process
- Model path from environment
- Health check via `/v1/models`
- No subprocess per request
- HTTP calls through a long-lived `httpx.AsyncClient`
- Shutdown cleanup in service lifecycle

Important implementation points:

```python
subprocess.Popen(["llama-server", ...])
GET /v1/models
POST /v1/chat/completions
```

## Existing Process Management Pattern

Inference service uses:

```text
ModelManager
  start_server()
  health()
  close()
```

This sprint mirrors that pattern in:

```text
tts/svara_llamacpp_runtime.py
```

## Runtime Design Decision

Implemented:

```text
TTSEngine
  ↑
SvaraTTSEngine
  ↓
SvaraRuntime
  ↓
llama-server-compatible speech endpoint
```

Why:

- Keeps gateway/API/cache/frontend untouched.
- Allows future TTS swaps.
- Keeps voice-service as runtime owner, not a second tutor implementation.
- Supports external runtime via `SVARA_SERVER_URL`.

## Important Runtime Boundary

The adapter requires a llama.cpp-compatible endpoint that returns WAV bytes or base64 WAV JSON.

Default:

```text
POST /v1/audio/speech
```

The adapter rejects non-WAV output and does not fabricate successful audio.

## Configuration Added

```text
VOICE_TTS_ENABLED
SVARA_MODEL_PATH
SVARA_THREADS
SVARA_CONTEXT
SVARA_GPU_LAYERS
SVARA_BATCH_SIZE
SVARA_TIMEOUT_SECONDS
SVARA_SERVER_HOST
SVARA_SERVER_PORT
SVARA_AUDIO_ENDPOINT
SVARA_SERVER_URL
SVARA_RUNTIME_METRICS_PATH
SVARA_WARMUP_ENABLED
```

## Reuse vs Duplication

Reused:

- Existing `TTSEngine`
- Existing `VoiceGateway`
- Existing audio storage
- Existing cache
- Existing Docker service model
- Existing inference-service persistent llama-server pattern

Not duplicated:

- Tutor/RAG pipeline
- Gateway proxy logic
- Audio storage abstraction
- Cache abstraction

## Audit Conclusion

The correct implementation path is a production runtime adapter behind `TTSEngine`, not direct Svara coupling.

Status after sprint:

```text
SvaraTTSEngine
-> SvaraRuntime
-> persistent llama.cpp-compatible runtime
-> WAV validation
-> existing AudioStorage
```

