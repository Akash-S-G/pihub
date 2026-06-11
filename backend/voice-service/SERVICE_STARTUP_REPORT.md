# Service Startup Report

Status: PASS

Command validated:

```bash
cd backend/voice-service
uvicorn app:app --host 127.0.0.1 --port 8050
```

Health probe: `200` in `49.931 ms`.

Response:

```json
{
  "status": "healthy",
  "service": "voice-service",
  "capabilities": {
    "voice_query": true,
    "stt": true,
    "tts": true,
    "streaming_tts": true,
    "pre_generated_audio": true,
    "range_requests": true
  }
}
```
