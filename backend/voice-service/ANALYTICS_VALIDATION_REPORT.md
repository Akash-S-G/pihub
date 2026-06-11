# Analytics Validation Report

Status: PARTIAL

Metrics endpoint is reachable. Request counters update for STT/TTS/voice query/cache misses. `streaming_sessions` is not currently emitted by the default HTTP path.

Missing expected counters after this run: `['audio_cache_hits', 'streaming_sessions']`

```json
{
  "method": "GET",
  "path": "/voice/metrics",
  "status_code": 200,
  "latency_ms": 24.259,
  "headers": {
    "date": "Thu, 11 Jun 2026 15:44:57 GMT",
    "server": "uvicorn",
    "content-length": "83",
    "content-type": "application/json"
  },
  "body": {
    "voice_query_requests": 2,
    "audio_cache_misses": 4,
    "stt_requests": 2,
    "tts_requests": 2
  }
}
```
