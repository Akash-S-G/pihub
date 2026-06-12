# Svara Runtime Certification Report

Generated: 2026-06-11

## Implementation Status

Implemented:

- Runtime config: `config/runtime.py`
- Runtime boundary: `tts/svara_llamacpp_runtime.py`
- `AudioResult` model
- `SvaraRuntime.warmup()`
- `SvaraRuntime.health_check()`
- `SvaraRuntime.synthesize()`
- `SvaraRuntime.synthesize_stream()` interface
- `SvaraTTSEngine` delegation to runtime
- Gateway support for runtime-provided `audio_id` and `duration_ms`
- Health endpoint TTS runtime status
- Runtime benchmark scaffold
- Dockerfile llama-server build stage
- Compose model mount and environment config

## Current Validation

### py_compile

Result: PASS

Checked:

```text
config/runtime.py
tts/svara_llamacpp_runtime.py
tts/svara_tts.py
services/voice_gateway.py
app.py
benchmarks/svara_runtime_benchmark.py
```

### Docker Compose Config

Result: PASS

```text
docker compose -f backend/docker-compose.yml config --quiet
```

### Targeted Docker Image Build

Result: PASS

```text
docker compose -f backend/docker-compose.yml build voice-service
```

Evidence:

```text
llama-server built successfully
backend-voice-service image built successfully
```

### Container Recreate

Result: BLOCKED BY COMMAND APPROVAL TIMEOUT

The rebuilt image was not started in this validation pass because both attempts to run:

```text
docker compose -f backend/docker-compose.yml up -d --no-deps --force-recreate voice-service
```

timed out in the command approval layer before execution.

### Disabled Runtime Health

Result: PASS

With:

```text
VOICE_TTS_ENABLED=false
```

Health returns:

```json
{
  "enabled": false,
  "loaded": false,
  "model": "svara-tts-v1.Q3_K_S.gguf",
  "status": "disabled"
}
```

### Missing Model Health

Result: PASS

With default enabled runtime and no mounted model:

```json
{
  "enabled": true,
  "loaded": false,
  "model": "svara-tts-v1.Q3_K_S.gguf",
  "model_path": "/models/svara/svara-tts-v1.Q3_K_S.gguf",
  "status": "missing_model"
}
```

### TTS API Cache Contract

Result: PASS

Validated with ASGI transport and fake TTS engine:

```text
Request 1 -> 200 cache_status=miss
Request 2 -> 200 cache_status=hit
```

## Model-Backed Certification

Result: NOT EXECUTED IN THIS ENVIRONMENT

Reason:

```text
No Svara GGUF model is mounted at /models/svara/svara-tts-v1.Q3_K_S.gguf in the current runtime.
```

The runtime is implemented, but real synthesis certification requires:

```text
SVARA_MODEL_PATH points to an existing Svara GGUF
llama-server supports the configured speech endpoint
POST /v1/audio/speech returns WAV bytes or base64 WAV JSON
```

## Certification Questions

### Can model load?

UNVERIFIED.

The runtime can start and health-check a llama.cpp-compatible server, but the model is not mounted here.

### Can model synthesize?

UNVERIFIED.

The adapter will call:

```text
POST {SVARA_SERVER_URL or localhost:SVARA_SERVER_PORT}/v1/audio/speech
```

and requires valid WAV output.

### Can API return audio?

PARTIAL.

The existing API/cache/storage path returns audio with a fake engine. Real Svara audio requires mounted model-backed runtime.

### Can cache store audio?

PASS.

Miss -> hit behavior is preserved.

### What is RTF?

UNVERIFIED.

Run:

```bash
cd backend/voice-service
python benchmarks/svara_runtime_benchmark.py
```

after mounting the model.

### What is peak RAM?

UNVERIFIED for real model.

The benchmark records `peak_ram_mb`.

### Expected GPU usage?

Configured via:

```text
SVARA_GPU_LAYERS=99
```

Actual VRAM depends on model quantization and host GPU.

## Final Verdict

```text
RUNTIME_ADAPTER_IMPLEMENTED
MODEL_BACKED_AUDIO_CERTIFICATION_PENDING
```

The sprint implementation is ready for a machine with the Svara GGUF mounted and a llama.cpp build that supports the configured speech endpoint.
