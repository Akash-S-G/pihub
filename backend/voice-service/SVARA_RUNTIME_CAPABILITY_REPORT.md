# Svara Runtime Capability Report

Generated: 2026-06-11

## Final Answer

```text
Can Svara GGUF generate WAV files through llama.cpp llama-server directly?

NO
```

Confidence: **high**

## Tested Model

```text
/home/akash/Desktop/voice-benchmark/svara_tts_gguf_benchmark/models/gguf/svara-tts-v1.Q3_K_S.gguf
```

## Live llama-server Validation

Command executed:

```bash
/home/akash/Desktop/AI/llama.cpp/build/bin/llama-server \
  --model /home/akash/Desktop/voice-benchmark/svara_tts_gguf_benchmark/models/gguf/svara-tts-v1.Q3_K_S.gguf \
  --host 127.0.0.1 \
  --port 18099 \
  --ctx-size 512 \
  --no-webui
```

### Model Load Result

Result: **PASS**

The model loads as a normal llama text-generation model:

```text
general.architecture = llama
general.name = Svara Tts v1
general.size_label = 3.3B
general.languages = ["hi", "bn", "mr", "te", "kn", ...]
model type = 3B
file type = Q3_K - Small
```

Important evidence:

```text
print_info: arch = llama
print_info: vocab type = BPE
main: model loaded
main: server is listening on http://127.0.0.1:18099
```

### GET /v1/models

Result: **PASS**

Response:

```json
{
  "models": [
    {
      "name": "svara-tts-v1.Q3_K_S.gguf",
      "model": "svara-tts-v1.Q3_K_S.gguf",
      "capabilities": ["completion"]
    }
  ]
}
```

Finding:

```text
The loaded Svara GGUF is exposed as a completion model, not an audio synthesis model.
```

### GET /docs

Result: **404**

Response:

```json
{
  "error": {
    "message": "File Not Found",
    "type": "not_found_error",
    "code": 404
  }
}
```

### GET /openapi.json

Result: **404**

Response:

```json
{
  "error": {
    "message": "File Not Found",
    "type": "not_found_error",
    "code": 404
  }
}
```

### POST /v1/audio/speech

Result: **404**

Request:

```json
{
  "model": "svara-tts-v1.Q3_K_S.gguf",
  "input": "Hello world",
  "voice": "en",
  "response_format": "wav"
}
```

Response:

```json
{
  "error": {
    "message": "File Not Found",
    "type": "not_found_error",
    "code": 404
  }
}
```

Finding:

```text
/v1/audio/speech is not available when llama-server is launched with only the Svara GGUF.
```

### POST /v1/completions

Result: **PASS**

Request:

```json
{
  "model": "svara-tts-v1.Q3_K_S.gguf",
  "prompt": "Hello world",
  "max_tokens": 16
}
```

Response excerpt:

```json
{
  "choices": [
    {
      "text": "!",
      "finish_reason": "stop"
    }
  ]
}
```

Finding:

```text
The model can generate text/discrete-token output through llama-server, but llama-server does not decode that output into WAV.
```

## llama.cpp Capability Evidence

Local llama.cpp source/doc evidence:

```text
/home/akash/Desktop/AI/llama.cpp/tools/tts/README.md
```

The llama.cpp TTS example requires:

```text
llama-tts -m <text-to-code model> -mv <wavtokenizer decoder model>
```

or, with server mode:

```text
llama-server -m <LLM model> --port 8020
llama-server -m <voice decoder model> --port 8021 --embeddings --pooling none
python tools/tts/tts-outetts.py http://localhost:8020 http://localhost:8021 "Hello world"
```

This means:

```text
llama-server alone is not the WAV-producing component for this class of TTS.
```

Local server documentation also states:

```text
--talker-model FILE enables the /v1/audio/speech endpoint
--code2wav-model FILE provides the talker code detokenizer
```

That path is documented for the qwen3-omni talker/code2wav stack, not for the Svara GGUF tested here.

Source route inspection:

```text
/home/akash/Desktop/AI/llama.cpp/tools/server/server.cpp
```

The server registers:

```text
/v1/audio/transcriptions
```

but the tested runtime did not expose:

```text
/v1/audio/speech
```

## Original Svara Project Evidence

Svara model card:

- The model is described as an Orpheus-style discrete audio token model.
- It is tagged for `discrete-audio-tokens`.
- It supports GGUF exports, but that does not imply llama-server directly emits audio.

Sources:

- https://huggingface.co/kenpath/svara-tts-v1
- https://huggingface.co/mradermacher/svara-tts-v1-GGUF

Reference inference repository:

```text
https://github.com/Kenpath/svara-tts-inference
```

The reference implementation describes:

```text
FastAPI Server
Embedded vLLM Engine
SNAC Decoder: Token -> PCM Audio
ffmpeg: PCM -> MP3/Opus/WAV/AAC
```

It exposes its own OpenAI-compatible endpoint:

```text
POST /v1/audio/speech
```

This endpoint is provided by the Svara inference server, not by vanilla llama-server with only the Svara GGUF.

## Local Benchmark Evidence

Existing local benchmark:

```text
/home/akash/Desktop/voice-benchmark/svara_tts_gguf_benchmark/run_gguf_benchmark.py
```

The benchmark uses:

```python
from llama_cpp import Llama
import onnxruntime as ort
```

Generation flow from local script:

```text
Svara GGUF
-> llama_cpp.Llama.generate()
-> discrete audio tokens
-> SNAC token grouping
-> ONNX SNAC decoder
-> PCM samples
-> soundfile writes WAV
```

Key evidence from script:

```text
SNAC_DECODER = models/snac_24khz-ONNX/on/decoder_model.onnx
decode_snac(...)
sf.write(audio_path, audio, SAMPLE_RATE)
```

Existing generated WAV files are valid:

```text
RIFF WAVE audio, PCM 16 bit, mono 24000 Hz
```

But they were not produced directly by `llama-server`.

## Does GGUF Export Preserve TTS Capability?

Answer:

```text
PARTIALLY
```

The GGUF preserves the text-to-discrete-audio-token model. Evidence:

- The local benchmark generated audio tokens.
- SNAC-decoded WAV files exist.
- The GGUF metadata identifies the model as `Svara Tts v1`.

But the GGUF alone does not contain the complete audio synthesis pipeline.

Missing from the single GGUF + llama-server path:

- SNAC decoder
- token-to-code mapping
- PCM/WAV conversion
- voice profile mapping
- chunking/stitching/crossfade
- format conversion

## Does llama.cpp Support the Required Architecture?

Answer:

```text
Not through vanilla llama-server with only Svara GGUF.
```

Supported pieces:

- llama.cpp can load the Svara GGUF as a llama completion model.
- llama.cpp has a separate `llama-tts` example for OuteTTS-style models.
- llama.cpp has server audio speech support for specific talker/code2wav model stacks.

Not supported by the tested path:

- `llama-server --model svara-tts-v1.Q3_K_S.gguf` does not expose `/v1/audio/speech`.
- It does not return WAV from `/v1/completions`.
- It reports only `completion` capability.

## Runtime Actually Required

A production Svara runtime should use one of these architectures.

### Recommended Architecture: Svara Inference Server Adapter

```text
Voice Service
-> SvaraHTTPRuntimeAdapter
-> Kenpath/svara-tts-inference FastAPI service
-> embedded vLLM engine
-> SNAC decoder
-> ffmpeg
-> WAV/MP3/Opus/AAC
```

Why:

- Matches the official reference architecture.
- Provides `/v1/audio/speech`.
- Handles SNAC decode and audio formatting.
- Supports streaming and voice IDs.
- Avoids reimplementing token-to-audio decoding inside IDP voice-service.

### Alternative Architecture: In-Process Local GGUF + SNAC Adapter

```text
Voice Service
-> SvaraLocalTokenRuntime
-> llama-cpp-python / llama.cpp generation
-> token parser
-> SNAC ONNX decoder
-> soundfile/ffmpeg
-> WAV
```

Why it works:

- Proven by local benchmark.
- Fully offline.

Tradeoffs:

- More code to own.
- Harder streaming.
- Need ONNX Runtime and SNAC decoder packaging.
- Need maintain token mapping and voice profiles.

### Not Recommended: Svara GGUF via vanilla llama-server only

```text
Voice Service
-> llama-server --model svara-tts-v1.Q3_K_S.gguf
-> /v1/audio/speech
-> WAV
```

Status:

```text
INVALID
```

Reason:

```text
/v1/audio/speech is 404 and the model is exposed only as completion-capable.
```

## Adapter Architecture Replacement

The current `SvaraRuntime` introduced in `VOICE-RUNTIME-1A` assumes a llama.cpp-compatible speech endpoint. That should be replaced with a provider-oriented adapter:

```python
TTSEngine
  -> SvaraTTSEngine
       -> SvaraRuntimeProvider
            -> SvaraInferenceServerProvider
            -> SvaraLocalSnacProvider
            -> FutureProvider
```

Concrete next adapter:

```text
SvaraInferenceServerProvider
```

Responsibilities:

- Call `POST /v1/audio/speech`
- Accept WAV/MP3/Opus/AAC
- Stream if requested
- Health-check `/health` and `/v1/voices`
- Keep voice-service API unchanged

Runtime service:

```text
backend/svara-runtime/
```

or external container:

```text
svara-runtime:
  image/build: Kenpath/svara-tts-inference compatible
  exposes: 8080
  gpu: optional/required depending deployment target
```

Voice service config should become:

```text
VOICE_TTS_PROVIDER=svara_http
SVARA_RUNTIME_URL=http://svara-runtime:8080
SVARA_DEFAULT_FORMAT=wav
```

## Final Verdict

```text
NO
```

Svara GGUF does **not** generate WAV files through `llama.cpp llama-server` directly when launched as:

```bash
llama-server --model svara-tts-v1.Q3_K_S.gguf
```

It can be loaded as a completion model and can generate discrete audio-token-like outputs, but real audio requires:

```text
SNAC decoder + token mapping + audio writer/ffmpeg
```

or the official/reference:

```text
Svara inference server with embedded vLLM + SNAC decoder + ffmpeg
```

