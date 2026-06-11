# Educational Chunking (Phase 1)

This package adds additive, modular semantic educational chunking for PIHUB.

## Modules

- `section_parser.py`: chapter/section segmentation
- `concept_boundary_detector.py`: pedagogical boundary detection
- `paragraph_merger.py`: short-paragraph continuity merging
- `educational_classifier.py`: chunk type classification
- `formula_preserver.py`: keeps equation-heavy blocks atomic
- `chunk_metadata_builder.py`: structured educational metadata
- `educational_chunker.py`: orchestration layer

## Smoke Test

```bash
cd backend/content-pipeline
python -m app.content_pipeline.chunking_smoke
```

The output lists chunk count and inferred chunk types.
