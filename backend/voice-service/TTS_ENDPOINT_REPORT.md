# TTS Endpoint Report

Status: PASS

Expected runtime boundary behavior: `501 Not Implemented` until Svara TTS is wired.

```json
{
  "method": "POST",
  "path": "/voice/tts",
  "status_code": 501,
  "latency_ms": 25.667,
  "headers": {
    "date": "Thu, 11 Jun 2026 15:44:57 GMT",
    "server": "uvicorn",
    "content-length": "131",
    "content-type": "application/json"
  },
  "body": {
    "detail": {
      "success": false,
      "error": {
        "code": "VOICE_RUNTIME_NOT_CONFIGURED",
        "message": "Svara TTS Q3_K_S runtime is not configured"
      }
    }
  }
}
```
