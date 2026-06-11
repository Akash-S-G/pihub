# Test Execution Report

Status: PASS

Command:

```bash
/tmp/voice-service-validation-venv/bin/python -m pytest backend/voice-service/tests -v
```

Result:

```text
5 passed, 1 warning in 0.47s
```

Output:

```text
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.0.3, pluggy-1.6.0 -- /tmp/voice-service-validation-venv/bin/python
cachedir: .pytest_cache
rootdir: /home/akash/Desktop/PIHUB
plugins: anyio-4.13.0
collecting ... collected 5 items

backend/voice-service/tests/test_voice_service.py::test_tts_cache_miss_then_hit PASSED [ 20%]
backend/voice-service/tests/test_voice_service.py::test_audio_retrieval_and_range_request PASSED [ 40%]
backend/voice-service/tests/test_voice_service.py::test_voice_query_cache_miss PASSED [ 60%]
backend/voice-service/tests/test_voice_service.py::test_stt_request PASSED [ 80%]
backend/voice-service/tests/test_voice_service.py::test_streaming_tts PASSED [100%]

========================= 5 passed, 1 warning in 0.47s =========================
```

Note: the plain sandboxed pytest command blocked under the local sandbox wrapper. The same suite completed successfully outside the sandbox using the validation virtual environment.
