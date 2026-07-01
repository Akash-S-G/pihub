# Audio Backend Benchmarking

Use `backend/certification/audio_backend_benchmark.py` to compare speech backends against the same manifest.

## Inputs

The benchmark expects a JSON manifest with entries like:

```json
[
  {
    "name": "classroom_en_01",
    "audio_path": "samples/classroom_en_01.wav",
    "reference": "What is Newton's second law?",
    "language": "en",
    "scenario": "clean",
    "tags": ["english", "classroom"]
  }
]
```

## Metrics

The tool reports:

- WER
- CER
- time to first partial
- final transcript latency
- CPU usage
- RAM usage
- model load time
- concurrent sessions
- English accuracy
- Hindi accuracy
- Kannada accuracy
- code-switching accuracy
- classroom noise robustness

## Runtime Contract

The benchmark uses the same in-process backends as the voice service:

- `FasterWhisperBackend`
- `Gemma4AudioBackend`

Gemma 4 Audio is exercised through the official Transformers runtime, and the benchmark captures the partial transcript stream emitted by the backend.
