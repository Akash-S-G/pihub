# TTS Cache Fix Report

Status: PASS

## Root Cause

The TTS gateway cached the first successful response correctly, but that cached response contained:

```text
cache_status = miss
```

On the second request, the gateway returned the cached payload without changing the status to:

```text
cache_status = hit
```

## Files Changed

```text
backend/voice-service/services/voice_gateway.py
```

## Lines Changed

Changed cache-hit return path:

```text
backend/voice-service/services/voice_gateway.py:89
```

Before:

```python
return TTSResponse.model_validate(cached)
```

After:

```python
return TTSResponse.model_validate(cached).model_copy(update={"cache_status": CacheStatus.hit})
```

## Before Flow

```text
Request 1
  cache lookup -> miss
  synthesize audio
  store audio
  cache response with cache_status=miss
  return miss

Request 2
  cache lookup -> hit
  return cached payload unchanged
  return miss
```

## After Flow

```text
Request 1
  cache lookup -> miss
  synthesize audio
  store audio
  cache response with cache_status=miss
  return miss

Request 2
  cache lookup -> hit
  validate cached payload
  override response metadata to cache_status=hit
  return hit
```

## Verification Probe

After the fix:

```json
{
  "key": "tts:en:default:wav:185f8db32271fe25f561a6fc938b2e264306ec304eda518007d1764826381969",
  "stored_cache_status": "CacheStatus.miss",
  "first_cache_status": "CacheStatus.miss",
  "second_cache_status": "CacheStatus.hit"
}
```

The stored object remains an accurate record of the original generation response, while the returned second response correctly reflects the cache-hit request path.

## Test Results

Command:

```bash
/tmp/voice-service-validation-venv/bin/python -m pytest backend/voice-service/tests -v
```

Result:

```text
5 passed, 1 warning in 0.47s
```

Detailed result:

```text
backend/voice-service/tests/test_voice_service.py::test_tts_cache_miss_then_hit PASSED
backend/voice-service/tests/test_voice_service.py::test_audio_retrieval_and_range_request PASSED
backend/voice-service/tests/test_voice_service.py::test_voice_query_cache_miss PASSED
backend/voice-service/tests/test_voice_service.py::test_stt_request PASSED
backend/voice-service/tests/test_voice_service.py::test_streaming_tts PASSED
```

## Notes

The plain sandboxed pytest command blocked under the local sandbox wrapper. The same suite completed successfully outside the sandbox using the existing validation virtual environment.
