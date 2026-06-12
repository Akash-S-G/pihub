# Voice Docker API Test Report

Generated: 2026-06-11

## Scope

Re-ran Docker/API validation for the integrated `voice-service` path:

```text
Client
-> nginx
-> gateway
-> voice-service
```

## Docker Build/Recreate

### Full compose rebuild

Result: **FAILED**

Command:

```bash
docker compose -f backend/docker-compose.yml up -d --build gateway voice-service nginx
```

Failure was unrelated to voice integration. Compose attempted to rebuild dependency services and `pack-service` failed dependency resolution:

```text
docling>=2.15.0 requires pydantic-settings>=2.3.0
pack-service pins pydantic-settings==2.1.0
```

### Targeted rebuild

Result: **PASS**

Command:

```bash
docker compose -f backend/docker-compose.yml build gateway voice-service
docker compose -f backend/docker-compose.yml up -d --no-deps --force-recreate gateway voice-service nginx
```

Recreated containers:

```text
pihub-voice-service
pihub-gateway
pihub-nginx
```

## Container Status

Result: **PASS**

```text
pihub-gateway        Up
pihub-nginx          Up, port 80 published
pihub-voice-service  Up, healthy
```

## Public API Validation

### GET /health

Result: **PASS**

```text
HTTP_STATUS=200
TIME_TOTAL=0.107200
```

Evidence:

```json
{
  "status": "healthy",
  "service": "gateway",
  "voice_service": {
    "healthy": true
  }
}
```

### GET /discovery

Result: **PASS**

```text
HTTP_STATUS=200
TIME_TOTAL=0.002094
```

Evidence:

```json
{
  "capabilities": {
    "voice": true,
    "audio": true
  },
  "supports_voice": true
}
```

### GET /api/voice/metrics

Result: **PASS**

```text
HTTP_STATUS=200
TIME_TOTAL=0.003906
```

Evidence:

```json
{
  "tts_requests": 1,
  "audio_cache_misses": 2,
  "voice_query_requests": 1,
  "stt_requests": 1
}
```

### POST /api/voice/tts

Result: **PASS - expected runtime boundary**

```text
HTTP_STATUS=501
TIME_TOTAL=0.005768
```

Evidence:

```json
{
  "detail": {
    "success": false,
    "error": {
      "code": "VOICE_RUNTIME_NOT_CONFIGURED",
      "message": "Svara TTS Q3_K_S runtime is not configured"
    }
  }
}
```

### POST /api/voice/stt

Result: **PASS - expected runtime boundary**

```text
HTTP_STATUS=501
TIME_TOTAL=0.009682
```

Evidence:

```json
{
  "detail": {
    "success": false,
    "error": {
      "code": "VOICE_RUNTIME_NOT_CONFIGURED",
      "message": "Distil-Whisper Large-v3 STT runtime is not configured"
    }
  }
}
```

### POST /api/voice/query

Result: **PASS - expected runtime boundary**

```text
HTTP_STATUS=501
TIME_TOTAL=11.337291
```

The request reached the voice query path and failed only when the service attempted to synthesize audio using the not-yet-configured TTS runtime.

### GET /api/voice/audio/missing.wav

Result: **PASS**

```text
HTTP_STATUS=404
TIME_TOTAL=0.003625
```

Evidence:

```json
{
  "detail": {
    "success": false,
    "error": {
      "code": "AUDIO_NOT_FOUND",
      "message": "missing.wav"
    }
  }
}
```

## OpenAPI Validation

Result: **PASS**

Fetched `http://127.0.0.1/openapi.json` with curl and verified these paths exist:

```json
{
  "/api/voice/query": true,
  "/api/voice/tts": true,
  "/api/voice/stt": true,
  "/api/voice/audio/{asset_id}": true,
  "/api/voice/metrics": true
}
```

## Internal Docker Network Validation

Result: **PASS**

From `pihub-gateway` container:

```text
http://voice-service:8050/health -> 200
http://voice-service:8050/voice/metrics -> 200
```

## Test Suite Status

### In-container pytest

Result: **BLOCKED**

Command:

```bash
docker exec pihub-voice-service python -m pytest tests -v
```

Observed:

```text
/usr/local/bin/python: No module named pytest
```

The runtime image does not include test dependencies.

### Host validation pytest

Result: **BLOCKED**

The host validation venv hangs at `fastapi.testclient.TestClient(app)` creation before any route is called. A bounded reproduction timed out after 15 seconds at:

```text
creating client
```

This appears to be a host validation dependency/runtime issue, not a Docker API route failure. Docker public API probes completed successfully.

## Final Result

Docker API validation: **PASS WITH EXPECTED RUNTIME BOUNDARIES**

Verified:

- `voice-service` container is healthy.
- Gateway health includes voice-service.
- Discovery advertises voice/audio.
- Nginx routes `/api/voice/*` through gateway.
- Gateway reaches `voice-service` over Docker internal DNS.
- Voice OpenAPI paths are present.
- TTS/STT/query endpoints return controlled `501` responses until runtime adapters are configured.
- Audio missing asset path returns controlled `404`.

Remaining blocker outside voice API integration:

- Full compose rebuild is blocked by `pack-service` dependency conflict between `docling` and `pydantic-settings`.
- Test dependencies are not installed inside the voice runtime image.
- Host `TestClient` validation environment currently hangs before request execution.
