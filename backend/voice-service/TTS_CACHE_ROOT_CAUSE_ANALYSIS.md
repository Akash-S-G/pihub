# TTS Cache Root Cause Analysis

Status: CONFIRMED

## Failing Behavior

`test_tts_cache_miss_then_hit` expected:

```text
POST /voice/tts request 1 -> cache_status = miss
POST /voice/tts request 2 -> cache_status = hit
```

Actual before fix:

```text
POST /voice/tts request 1 -> cache_status = miss
POST /voice/tts request 2 -> cache_status = miss
```

## Execution Path

```text
POST /voice/tts
  -> api/routes.py:17
  -> voice_tts()
  -> services/voice_gateway.py:82
  -> VoiceGateway.tts_only()
  -> cache lookup
  -> TTS generation
  -> audio storage write
  -> cache write
  -> response
```

Route:

```text
backend/voice-service/api/routes.py:17-23
```

Gateway:

```text
backend/voice-service/services/voice_gateway.py:82-97
```

Cache:

```text
backend/voice-service/cache/voice_cache.py:31-42
```

## Cache Write Verification

`cache.set(...)` is called after successful synthesis:

```text
backend/voice-service/services/voice_gateway.py:95-96
```

```python
if request.cache:
    await self.cache.set(key, response.model_dump(), ttl_seconds=3600)
```

So the root cause is not a missing cache write.

## Cache Key Verification

Probe request:

```json
{
  "text": "Hello",
  "language": "en",
  "cache": true
}
```

Observed key:

```text
tts:en:default:wav:185f8db32271fe25f561a6fc938b2e264306ec304eda518007d1764826381969
```

Result:

```json
{
  "request1_key": "tts:en:default:wav:185f8db32271fe25f561a6fc938b2e264306ec304eda518007d1764826381969",
  "request2_key": "tts:en:default:wav:185f8db32271fe25f561a6fc938b2e264306ec304eda518007d1764826381969",
  "keys_equal": true
}
```

So the root cause is not wrong cache key generation.

## Cache Storage Verification

Immediately after the first generation, `cache.get(key)` returned:

```json
{
  "success": true,
  "audio_id": "tts_ce11b6d1feb41f9fdcf958f2",
  "audio_url": "/voice/audio/tts_ce11b6d1feb41f9fdcf958f2",
  "cache_status": "miss",
  "format": "wav",
  "duration_ms": null
}
```

So the cache object is not recreated per request, and TTL is not expiring.

## Root Cause

Category:

```text
Response bypasses cache-hit status normalization
```

The cached object was stored with the first response status:

```text
cache_status = miss
```

On cache hit, the gateway returned the cached payload directly:

```python
return TTSResponse.model_validate(cached)
```

That preserved the stored `miss` value, even though the second response was served from cache.

## Conclusion

The cache lookup and cache write both worked. The defect was that the TTS cache-hit branch did not override the response metadata to reflect the current request path.
