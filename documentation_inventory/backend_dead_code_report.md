# Backend Dead Code Report
*Generated: 2026-06-09*

---

## Overview

This report identifies candidates for dead, stale, or potentially unused code across the backend. Confidence levels: **High** (very likely dead), **Medium** (probably dead, needs audit), **Low** (may be used, needs review).

---

## High Confidence Dead Code

| # | Path | Type | Reason |
|---|------|------|--------|
| 1 | `backend/.venv/` | Directory | Virtual environment, not source code |
| 2 | `backend/content-pipeline/app/**/__pycache__/` | Directory | Build artifacts |
| 3 | `backend/experiment-service/**/__pycache__/` | Directory | Build artifacts |
| 4 | `backend/pack-service/**/__pycache__/` | Directory | Build artifacts |
| 5 | `backend/pihub/**/__pycache__/` | Directory | Build artifacts |
| 6 | `backend/gateway/**/__pycache__/` | Directory | Build artifacts |
| 7 | `backend/inference-service/**/__pycache__/` | Directory | Build artifacts |
| 8 | `debug_script.py` | Script | One-off debug script at root level |
| 9 | `backend/pack-service/app/api/preview_routes.py` | Module | Internal debug only |

---

## Medium Confidence Dead Code

| # | Path | Type | Reason |
|---|------|------|--------|
| 1 | `backend/content_pipeline/` | Module | Duplicate of `content-pipeline/` (no hyphen). Check which is used. |
| 2 | `backend/pack-service/app/api/pack_response_models.py` | Module | May be unused if routes define models inline. Verify imports. |
| 3 | `backend/curriculum-builder/build_cache.json` | Data | Stale cache file. Verify freshness. |
| 4 | `backend/scripts/regenerate_damaged_packs.py` | Script | One-time recovery script. OK to archive. |
| 5 | `backend/scripts/repair_legacy_pack_from_qdrant.py` | Script | One-time repair script. OK to archive. |
| 6 | `backend/content_forensics/run_grade8_forensics.py` | Script | One-off grade 8 audit. OK to archive. |
| 7 | `backend/content_forensics/run_multi_grade_regeneration.py` | Script | One-time script. OK to archive. |
| 8 | `backend/shared/topic_normalization.py` | Module | Potentially unused. Check imports across codebase. |
| 9 | `backend/content_forensics/source_chunk_classifier.py` | Script | Check if still used for ongoing classification. |

---

## Low Confidence Dead Code

| # | Path | Type | Reason |
|---|------|------|--------|
| 1 | `backend/scripts/performance_benchmark.py` | Script | Benchmark scripts may be run ad-hoc. Verify. |
| 2 | `backend/scripts/ai_content_generation_quality_audit.py` | Script | May be scheduled. Verify frequency. |
| 3 | `backend/scripts/semantic_content_pipeline_audit.py` | Script | May be scheduled. Verify frequency. |
| 4 | `backend/scripts/integration_test_suite.py` | Script | May be used in CI. Verify. |
|ingredient 5 | `backend/pack-service/app/pack_storage/` | Module | Check if still in use or superseded by new API. |
| 6 | `backend/experiment-service/app/storage/seed_experiments.json` | Data | Seed file. Verify if used on startup. |
| 7 | `backend/experiment-service/tests/` | Tests | Check test execution. |
| 8 | `backend/pack-service/tests/` | Tests | Check test execution. |
| 9 | `backend/content-pipeline/tests/` | Tests | Check test execution. |

---

## .venv Artifacts (Non-Source)

| # | Path | Count |
|---|------|-------|
| 1 | `backend/.venv/lib/python3.12/site-packages/` | ~650 directories |
| 2 | `backend/.venv/lib64/python3.12/site-packages/` | ~650 directories |
| 3 | `.venv/lib/python3.12/site-packages/` | ~650 directories |
| 4 | `.venv/lib64/python3.12/site-packages/` | ~650 directories |

These are virtual environment packages and should **not** be committed to repo.

---

## Forensic / Audit Scripts (Ephemeral)

These are run once for specific audits. Consider archiving to a dedicated `archive/` folder or marking with a comment.

| # | Path | Purpose |
|---|------|---------|
| 1 | `cleanup_loss_audit.py` | Cleanup loss audit |
| 2 | `deduplication_loss_audit.py` | Deduplication loss |
| 3 | `formula_retention_audit.py` | Formula retention |
| 4 | `concept_loss_root_cause.py` | Concept loss root cause |
| 5 | `qdrant_retrieval_audit.py` | Qdrant retrieval audit |
| 6 | `run_concept_precision_recovery.py` | Concept precision recovery |
| 7 | `run_explanation_recovery_pilot.py` | Explanation recovery pilot |
| 8 | `run_formula_intelligence_validation.py` | Formula validation |
| 9 | `run_full_corpus_regeneration.py` | Full corpus regeneration |
| 10 | `run_source_corpus_audit.py` | Source corpus audit |
| 11 | `run_structure_extraction_benchmark.py` | Structure benchmark |
| 12 | `run_tutor_context_validation.py` | Tutor context validation |
| 13 | `run_worked_example_validation.py` | Worked example validation |
| 14 | `run_quality_gate_closure_validation.py` | Quality gate closure |
| 15 | `run_grade8_full_regeneration.py` | Grade 8 regeneration |

---

## Cleanup Recommendations

| # | Action | Impact |
|---|--------|--------|
| 1 | Remove all `__pycache__/` from repo | Low risk |
| 2 | Add `__pycache__/` to `.gitignore` | Prevents future commits |
| 3 | Remove `backend/.venv/` from repo | **NEVER** commit venv |
| 4 | Archive one-time forensic scripts | Keep in `archive/` or just delete |
| 5 | Audit `content_pipeline/` vs `content-pipeline/` | Keep one, remove duplicate |
| 6 | Verify `preview_routes.py` in production | Gate with env var if needed |
| 7 | Clean up TEMP/ directory | Large binary artifacts |
| 8 | Review `backend/scripts/` for schedule | Only keep actively used scripts |

---

## Potential Savings

| Category | Estimated Size | Risk |
|----------|---------------|------|
| `__pycache__/` directories | ~10-50 MB | Zero |
| `.venv/` directories | ~2-5 GB | Zero (should be in .gitignore) |
| One-time forensic scripts | ~2-5 MB | Low (archive first) |
| Stale cache/Temp files | ~500 MB | Low |
| Duplicated `content_pipeline` | ~5 MB | Medium (verify first) |

---

*End of Backend Dead Code Report*
