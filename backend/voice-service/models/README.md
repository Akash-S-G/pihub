# Voice Model Assets

Place the Svara GGUF model here so the voice container can mount it directly.

Expected runtime path inside the container:

```text
/models/svara/svara-tts-v1.Q4_K_M.gguf
```

The SNAC decoder stays in the existing `snac_24khz-ONNX/onnx/` subdirectory.

This folder is ignored by git for large binary artifacts, so the model can live
here on disk without being committed.
