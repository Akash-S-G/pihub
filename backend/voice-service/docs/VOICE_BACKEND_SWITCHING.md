# Voice Backend Switching

This document describes the pluggable speech-recognition backend used by the voice service.

## Goal

Keep the Android websocket protocol unchanged while allowing the service to switch between:

- `faster_whisper`
- `gemma4_audio`

The rest of the pipeline stays the same:

```text
Audio -> STT backend -> transcript -> curriculum retrieval -> tutor -> TTS -> audio
```

## Backend Interface

The active backend implements:

- `initialize()`
- `transcribe_stream()`
- `transcribe()`
- `health()`
- `metrics()`
- `shutdown()`

## Selection

Set one environment variable:

```text
VOICE_BACKEND=faster_whisper
VOICE_BACKEND=gemma4_audio
```

If `VOICE_BACKEND=gemma4_audio`, the service uses:

- `Gemma4AudioBackend` as primary
- `FasterWhisperBackend` as automatic fallback

## Fallback

When the primary backend fails, the service logs:

```text
VOICE_BACKEND_FALLBACK reason=...
```

Then it switches to the fallback backend without restarting the service.

## Gemma Model Cache

The Gemma backend uses the Hugging Face cache directory:

```text
/models/gemma4_audio
```

Default model id:

```text
google/gemma-4-E4B-it
```

The backend runs the official Gemma 4 multimodal Transformers runtime directly.

## Health Fields

The `/health` response now exposes:

- `voice_backend`
- `backend_loaded`
- `streaming_supported`
- `fallback_active`
- `model_name`
- `backend_latency`
- `last_error`

## Websocket Compatibility

The websocket protocol is unchanged. The service still accepts:

- `session_start` / `audio_start`
- `audio_chunk`
- `audio_complete`

And it may emit additional progress events such as:

- `partial_transcript`
- `final_transcript`
- `response_chunk`
- `response_complete`
- `generating_audio`
- `audio_chunk`
- `audio_complete`

Those are additive and do not require Android changes.
