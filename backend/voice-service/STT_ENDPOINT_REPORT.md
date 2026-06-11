# STT Endpoint Report

Status: PASS

Expected runtime boundary behavior: `501 Not Implemented` until Distil-Whisper is wired.

```json
{
  "method": "POST",
  "path": "/voice/stt?language=en&enable_partial_transcripts=true",
  "status_code": 501,
  "latency_ms": 22.692,
  "headers": {
    "date": "Thu, 11 Jun 2026 15:44:57 GMT",
    "server": "uvicorn",
    "content-length": "142",
    "content-type": "application/json"
  },
  "body": {
    "detail": {
      "success": false,
      "error": {
        "code": "VOICE_RUNTIME_NOT_CONFIGURED",
        "message": "Distil-Whisper Large-v3 STT runtime is not configured"
      }
    }
  }
}
```
