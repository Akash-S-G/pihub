# Svara Runtime Benchmark

Generated: 2026-06-11

Status: **NOT EXECUTED**

Reason:

```text
No Svara GGUF model is mounted at /models/svara/svara-tts-v1.Q3_K_S.gguf in the current runtime.
```

Benchmark runner added:

```text
benchmarks/svara_runtime_benchmark.py
```

Run after mounting the model:

```bash
cd backend/voice-service
python benchmarks/svara_runtime_benchmark.py
```

The benchmark measures:

- 20 word generation
- 50 word generation
- 100 word generation
- 250 word generation
- generation time
- real-time factor
- peak RAM
- audio size

Expected output:

```text
SVARA_RUNTIME_BENCHMARK.md
```

with measured rows for each benchmark case.
