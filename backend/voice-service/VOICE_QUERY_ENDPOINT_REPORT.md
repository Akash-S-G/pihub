# Voice Query Endpoint Report

Status: PARTIAL

The endpoint is reachable and returns the expected runtime-boundary error because the Gemma/RAG tutor runtime is intentionally not wired yet.

```json
{
  "method": "POST",
  "path": "/voice/query",
  "status_code": 501,
  "latency_ms": 18.538,
  "headers": {
    "date": "Thu, 11 Jun 2026 15:44:57 GMT",
    "server": "uvicorn",
    "content-length": "147",
    "content-type": "application/json"
  },
  "body": {
    "detail": {
      "success": false,
      "error": {
        "code": "VOICE_RUNTIME_NOT_CONFIGURED",
        "message": "Gemma 4 12B curriculum RAG tutor runtime is not configured"
      }
    }
  }
}
```
