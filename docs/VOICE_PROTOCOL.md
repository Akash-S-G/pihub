# Voice Protocol

This document defines the WebSocket communication protocol contract between the client (Flutter) and the server (Voice Gateway & Voice Service).

## Protocol Overview

All messages are JSON objects containing a `type` field.

### Client → Server Messages

#### 1. `audio_start`
Initiates a new voice session.
```json
{
  "type": "audio_start",
  "session_id": "session-123"
}
```

#### 2. `audio_chunk`
Sends base64-encoded audio frames.
```json
{
  "type": "audio_chunk",
  "sequence": 1,
  "data": "SGVsbG8="
}
```

#### 3. `audio_complete`
Indicates audio stream completion, requesting transcription and tutor synthesis.
```json
{
  "type": "audio_complete",
  "language": "kn",
  "simulation_context": {
    "experiment_id": "heart_rate_v2"
  }
}
```

---

### Server → Client Messages

#### 1. `partial_transcript`
Intermediate transcription feedback.
```json
{
  "type": "partial_transcript",
  "text": "Processing..."
}
```

#### 2. `final_transcript`
Final speech-to-text transcription result.
```json
{
  "type": "final_transcript",
  "text": "What is photosynthesis?"
}
```

#### 3. `response_chunk`
Streaming text reply chunks from the tutor model.
```json
{
  "type": "response_chunk",
  "text": "Photosynthesis is"
}
```

#### 4. `response_complete`
Signifies the end of the text answer stream.
```json
{
  "type": "response_complete"
}
```

#### 5. `audio_ready`
Provides a URL to fetch the synthesized audio playback.
```json
{
  "type": "audio_ready",
  "audio_url": "/mock/audio.wav"
}
```

#### 6. `error`
Standard error format.
```json
{
  "type": "error",
  "message": "Connection closed unexpectedly."
}
```
