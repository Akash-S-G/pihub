# Svara Local Provider Certification

## Verdict

PARTIAL

The production runtime boundary has been replaced with a local Svara provider using:

```text
GGUF
llama_cpp.Llama
SNAC ONNX decoder
soundfile WAV writing
```

The previous `llama-server` and `/v1/audio/speech` assumption has been removed from active code.

## Files Created

```text
backend/voice-service/tts/providers/__init__.py
backend/voice-service/tts/providers/svara_local_provider.py
backend/voice-service/SVARA_LOCAL_PROVIDER_CERTIFICATION.md
```

## Files Modified

```text
backend/voice-service/config/runtime.py
backend/voice-service/tts/svara_tts.py
backend/voice-service/tts/__init__.py
backend/voice-service/services/voice_gateway.py
backend/voice-service/benchmarks/svara_runtime_benchmark.py
backend/voice-service/requirements.txt
backend/voice-service/Dockerfile
backend/docker-compose.yml
backend/.env.example
```

## Files Removed

```text
backend/voice-service/tts/svara_llamacpp_runtime.py
```

Reason: the old adapter assumed a llama-server speech endpoint, which the runtime capability audit proved invalid for Svara GGUF.

## Runtime Architecture

```text
TTSEngine
  -> SvaraTTSEngine
      -> SvaraLocalProvider
          -> llama_cpp.Llama persistent GGUF model
          -> SNAC ONNX decoder
          -> soundfile WAV writer
          -> AudioResult
      -> VoiceGateway
      -> AudioStorage
      -> VoiceCache
```

## Configuration

Added environment-driven local runtime settings:

```text
SVARA_GGUF_PATH
SVARA_SNAC_DECODER_PATH
SVARA_SAMPLE_RATE
SVARA_MAX_TOKENS
SVARA_THREADS
SVARA_CONTEXT
SVARA_GPU_LAYERS
SVARA_BATCH_SIZE
SVARA_TIMEOUT_SECONDS
```

No model path is hardcoded in the provider.

## Implemented Behavior

### Persistent Loading

`SvaraLocalProvider.ensure_loaded()` loads:

```text
llama_cpp.Llama(...)
onnxruntime.InferenceSession(...)
```

once per service process.

### Token Generation

The provider reuses the proven benchmark algorithm:

```text
voice + text
-> prompt tokens
-> llama_cpp generated tokens
-> Svara discrete audio token range
```

### SNAC Decode

The provider groups Svara audio tokens into:

```text
audio_codes.0
audio_codes.1
audio_codes.2
```

and calls the SNAC ONNX decoder.

### WAV Writing

The provider writes:

```text
tts_<sha256>.wav
```

to:

```text
SVARA_GENERATED_AUDIO_DIR
```

defaulting to:

```text
/tmp/idp_voice_audio/generated
```

### Health

`GET /health` now receives TTS health from `SvaraLocalProvider`:

```json
{
  "provider": "svara_local",
  "gguf_loaded": true,
  "snac_loaded": true
}
```

when both runtime artifacts and dependencies are present.

## Validation Results

### py_compile

PASS

Command:

```text
python3 -m py_compile backend/voice-service/config/runtime.py backend/voice-service/tts/providers/svara_local_provider.py backend/voice-service/tts/svara_tts.py backend/voice-service/tts/__init__.py backend/voice-service/services/voice_gateway.py backend/voice-service/app.py backend/voice-service/benchmarks/svara_runtime_benchmark.py
```

Result:

```text
0 errors
```

### Cache Contract

PASS

Direct gateway validation with fake TTS:

```json
{
  "first": "miss",
  "second": "hit",
  "audio_id_same": true
}
```

### Missing Model Health

PASS

When model files are not mounted at default container paths:

```json
{
  "provider": "svara_local",
  "enabled": true,
  "gguf_loaded": false,
  "snac_loaded": false,
  "status": "missing_model_or_decoder"
}
```

### Real Local Svara Run

PARTIAL

Attempted with:

```text
SVARA_GGUF_PATH=/home/akash/Desktop/voice-benchmark/svara_tts_gguf_benchmark/models/gguf/svara-tts-v1.Q3_K_S.gguf
SVARA_SNAC_DECODER_PATH=/home/akash/Desktop/voice-benchmark/svara_tts_onnx_benchmark/models/snac_24khz-ONNX/onnx/decoder_model.onnx
SVARA_MAX_TOKENS=60
SVARA_GPU_LAYERS=0
```

Observed:

```text
llama_context: n_ctx_seq (4096) < n_ctx_train (131072) -- the full capacity of the model will not be utilized
```

The model entered the llama.cpp context path, but the CPU-only synthesis attempt did not complete within the validation window. No WAV was produced during this run.

This means the implementation is wired, but real playable WAV certification is not complete in the current shell/runtime environment.

### pytest

BLOCKED

System pytest has no `httpx`.

Repo venvs have FastAPI/httpx but no pytest.

Mixed Python-version site-packages caused runtime incompatibilities. A direct gateway cache validation was run instead and passed.

## Answers

Can GGUF load?

PARTIAL. The real model entered llama.cpp context setup; complete load/generation certification did not finish in the current CPU validation window.

Can SNAC load?

IMPLEMENTED. SNAC loading is implemented via `onnxruntime.InferenceSession`. Full runtime validation requires a single environment containing compatible `fastapi`, `llama_cpp`, `onnxruntime`, `soundfile`, and `pytest` dependencies.

Can WAV be generated?

IMPLEMENTED BUT NOT CERTIFIED IN THIS RUN. The WAV generation code path is implemented using `soundfile`, but the live Svara synthesis attempt timed out before a WAV was emitted.

Can API return audio?

CODE PATH IMPLEMENTED. `VoiceGateway` now supports `AudioResult.file_path`, stores the WAV bytes through `AudioStorage`, and returns the existing `audio_url` contract. Live API validation with real Svara audio remains pending.

Can cache work?

YES. Direct validation returned first request `miss`, second request `hit`.

What is peak RAM?

Not certified in this run. The benchmark script records `peak_ram_mb` when the runtime completes.

What is average latency?

Not certified in this run. The local CPU validation did not complete within the validation window.

## Remaining Certification Work

Run the benchmark or API validation inside a single clean voice-service environment with:

```text
fastapi
httpx
pytest
llama-cpp-python
onnxruntime
soundfile
numpy
psutil
```

and mounted files:

```text
/models/svara/svara-tts-v1.Q3_K_S.gguf
/models/svara/snac_24khz-ONNX/onnx/decoder_model.onnx
```

Then execute:

```text
python benchmarks/svara_runtime_benchmark.py
```

and:

```text
POST /api/voice/tts
```

through the gateway.
