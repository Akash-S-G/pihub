# Backend Component Map
*Generated: 2026-06-09*

---

## Overview

This document maps every significant Python module in the backend codebase to its architectural role, service, and key responsibilities.

---

## 1. Gateway Components

| Component | Path | Role |
|-----------|------|------|
| Gateway Main | `backend/gateway/app/main.py` | Entry point for all client traffic |
| Experiment Client | `backend/gateway/app/services/experiment_service_client.py` | Forwards experiment requests to experiment-service |

---

## 2. Content Pipeline Components

| Component | Path | Role |
|-----------|------|------|
| Main | `backend/content-pipeline/app/main.py` | Service entry point (health, ingest, RAG) |
| Auto Ingest | `backend/content-pipeline/app/auto_ingest.py` | Automated content ingestion pipeline |
| Educational Chunker | `backend/content-pipeline/app/content_pipeline/educational_chunker.py` | Pedagogically-aware chunking |
| Chunk Metadata Builder | `backend/content-pipeline/app/content_pipeline/chunk_metadata_builder.py` | Builds chunk metadata |
| Section Parser | `backend/content-pipeline/app/content_pipeline/section_parser.py` | Parses textbook sections |
| Extraction Cleaner | `backend/content-pipeline/app/content_pipeline/extraction_cleaner.py` | Cleans extracted text |
| Concept Boundary Detector | `backend/content-pipeline/app/content_pipeline/concept_boundary_detector.py` | Detects concept spans |
| Paragraph Merger | `backend/content-pipeline/app/content_pipeline/paragraph_merger.py` | Merges short paragraphs |
| Formula Preserver | `backend/content-pipeline/app/content_pipeline/formula_preserver.py` | Protects math during chunking |
| Chunking Smoke | `backend/content-pipeline/app/content_pipeline/chunking_smoke.py` | Smoke test for chunking |
| Curriculum Router | `backend/content-pipeline/app/curriculum_graph/curriculum_router.py` | Routes curriculum queries |
| Concept Index | `backend/content-pipeline/app/curriculum_graph/concept_index.py` | Concept lookup index |
| Concept Linker | `backend/content-pipeline/app/curriculum_graph/concept_linker.py` | Links concepts across content |
| Prerequisite Mapper | `backend/content-pipeline/app/curriculum_graph/prerequisite_mapper.py` | Maps prerequisite chains |
| Graph Builder | `backend/content-pipeline/app/curriculum_graph/graph_builder.py` | Builds concept graph |
| Graph Storage | `backend/content-pipeline/app/curriculum_graph/graph_storage.py` | Persists graph |
| Topic Relation Builder | `backend/content-pipeline/app/curriculum_graph/topic_relation_builder.py` | Topic-to-topic relations |
| Enrichment Router | `backend/content-pipeline/app/educational_intelligence/enrichment_router.py` | Routes to enrichment generators |
| Flashcard Generator | `backend/content-pipeline/app/educational_intelligence/flashcard_generator.py` | Generates flashcards |
| Quiz Generator | `backend/content-pipeline/app/educational_intelligence/quiz_generator.py` | Generates quizzes |
| Summary Generator | `backend/content-pipeline/app/educational_intelligence/summary_generator.py` | Generates summaries |
| Glossary Extractor | `backend/content-pipeline/app/educational_intelligence/glossary_extractor.py` | Extracts definitions |
| Quality Evaluator | `backend/content-pipeline/app/educational_intelligence/quality_evaluator.py` | Scores enrichment quality |
| Pack Compiler | `backend/content-pipeline/app/educational_intelligence/pack_compiler.py` | Bundles to .otpack |
| Multilingual Support | `backend/content-pipeline/app/educational_intelligence/multilingual_support.py` | Translation layer |
| Retrieval Engine | `backend/content-pipeline/app/retrieval_engine/educational_retrieval_engine.py` | RAG search engine |
| Textbook Ingest | `backend/content-pipeline/app/textbook_ingest.py` | Textbook ingestion orchestrator |

---

## 3. Pack Service Components

| Component | Path | Role |
|-----------|------|------|
| Main | `backend/pack-service/app/main.py` | Service entry point |
| Pack Routes | `backend/pack-service/app/api/pack_routes.py` | REST API for packs |
| PDF Routes | `backend/pack-service/app/api/pdf_routes.py` | API for PDF catalog & reader |
| Preview Routes | `backend/pack-service/app/api/preview_routes.py` | Debug preview routes |
| Pack Download | `backend/pack-service/app/api/pack_download_service.py` | Serve .otpack files |
| Response Models | `backend/pack-service/app/api/pack_response_models.py` | Pydantic schemas for packs |
| Chunk Normalizer | `backend/pack-service/app/educational/chunk_normalizer.py` | Normalizes chunk structure |
| Concept Coverage Valid. | `backend/pack-service/app/educational/concept_coverage_validator.py` | Validates concept coverage |
| Concept Extractor | `backend/pack-service/app/educational/concept_extractor.py` | Extracts concepts from text |
| Concept Graph | `backend/pack-service/app/educational/concept_graph.py` | Graph of concepts |
| Concept Models | `backend/pack-service/app/educational/concept_models.py` | Pydantic models for concepts |
| Explanation Recovery | `backend/pack-service/app/educational/explanation_recovery.py` | Recovers missing explanations |
| Formula Intelligence | `backend/pack-service/app/educational/formula_intelligence.py` | Formula handling |
| Learning Objective Ext. | `backend/pack-service/app/educational/learning_objective_extractor.py` | Extracts LOs |
| Structure Parser | `backend/pack-service/app/educational/structure_parser.py` | Parses structural elements |
| Textbook Builder | `backend/pack-service/app/educational/textbook_builder.py` | Assembles textbook structure |
| Textbook Models | `backend/pack-service/app/educational/textbook_models.py` | Models for textbooks |
| TOC Cleanup | `backend/pack-service/app/educational/toc_cleanup.py` | Cleans TOC data |
| Tutor Context Builder | `backend/pack-service/app/educational/tutor_context_builder.py` | Builds tutor context |
| Worked Example Builder | `backend/pack-service/app/educational/worked_example_builder.py` | Builds worked examples |
| Checksum Generator | `backend/pack-service/app/pack_system/checksum_generator.py` | Generates pack checksums |
| Manifest Builder | `backend/pack-service/app/pack_system/manifest_builder.py` | Builds manifest.yml |
| Manifest Validator | `backend/pack-service/app/pack_system/manifest_validator.py` | Validates manifest structure |
| Version Manager | `backend/pack-service/app/pack_system/version_manager.py` | Pack versioning |
| Pack Metadata Store | `backend/pack-service/app/pack_system/pack_metadata_store.py` | Metadata persistence |
| PDF Registration | `backend/pack-service/app/pdf_reader/pdf_registration_service.py` | Registers PDFs |
| PDF Repository | `backend/pack-service/app/pdf_reader/pdf_repository.py` | PDF data access |
| Chapter Page Mapper | `backend/pack-service/app/pdf_reader/chapter_page_mapper.py` | Maps chapters to pages |
| Delta Builder | `backend/pack-service/app/sync/delta_builder.py` | Builds diffs between packs versions |
| Sync Manifest Gen. | `backend/pack-service/app/sync/sync_manifest_generator.py` | Generates sync manifest |
| Educational Quality Val. | `backend/pack-service/app/validation/educational_quality_validator.py` | Validates educational quality |
| Pack Validator | `backend/pack-service/app/validation/pack_validator.py` | Validates .otpack structure |
| Quiz Validator | `backend/pack-service/app/validation/quiz_validator.py` | Validates quiz correctness |
| Retrieval Validator | `backend/pack-service/app/validation/retrieval_validator.py` | Validates search quality |

---

## 4. Experiment Service Components

| Component | Path | Role |
|-----------|------|------|
| Main | `backend/experiment-service/app/main.py` | Service entry |
| Core DB | `backend/experiment-service/app/core/database.py` | Database connection |
| Core Errors | `backend/experiment-service/app/core/errors.py` | Custom exceptions |
| Core Pagination | `backend/experiment-service/app/core/pagination.py` | Pagination helpers |
| Core Observability | `backend/experiment-service/app/core/observability.py` | Logging / metrics |
| Core Payload Limits | `backend/experiment-service/app/core/payload_limits.py` | Request size limits |
| API Routes | `backend/experiment-service/api/routes.py` | Main REST API routes |
| Builder Routes | `backend/experiment-service/app/builder/routes.py` | Builder API |
| Classroom Routes | `backend/experiment-service/app/classroom/routes.py` | Classroom API |
| AI Routes | `backend/experiment-service/app/ai/routes.py` | AI experiment API |
| Maintenance Routes | `backend/experiment-service/app/maintenance/routes.py` | Health / audit routes |
| Manifest Routes | `backend/experiment-service/app/manifest/routes.py` | Manifest API |
| Experiment Content Routes | `backend/experiment-service/app/experiment_content/routes.py` | Content API |
| Sharing Routes | `backend/experiment-service/app/sharing/routes.py` | Sharing API |
| AI Generator | `backend/experiment-service/app/ai/services/ai_experiment_generator_service.py` | AI experiment generation |
| AI Providers | `backend/experiment-service/app/ai/services/providers.py` | LLM provider abstraction |
| Classroom Service | `backend/experiment-service/app/classroom/services/classroom_service.py` | Classroom logic |
| Classroom Repository | `backend/experiment-service/app/classroom/repositories/classroom_repository.py` | Classroom data access |
| Execution Resolver | `backend/experiment-service/app/services/execution_resolver.py` | Resolves execution plans |
| Manifest Resolver | `backend/experiment-service/app/services/manifest_resolver.py` | Resolves manifest references |
| Manifest Migration | `backend/experiment-service/app/services/manifest_migration_service.py` | Manifest migration |
| Manifest Version | `backend/experiment-service/app/services/manifest_version_service.py` | Version management |
| Execution Package | `backend/experiment-service/app/services/execution_package_service.py` | Execution packaging |
| Experiment Registry | `backend/experiment-service/services/experiment_registry.py` | Registry of experiments |
| Experiment Run Svc | `backend/experiment-service/services/experiment_run_service.py` | Manages runs |
| Run Repository | `backend/experiment-service/repositories/run_repository.py` | Run data access |
| Experiment Manifest | `backend/experiment-service/repositories/experiment_manifest_repository.py` | Manifest data access |
| Manifest Template | `backend/experiment-service/app/manifest/template_repository.py` | Template data access |
| Manifest Storage | `backend/experiment-service/app/services/manifest_storage_service.py` | Manifest storage |
| Manifest Validator | `backend/experiment-service/app/manifest/validator.py` | Manifest validation |
| Manifest Migrations | `backend/experiment-service/app/manifest/migrations.py` | DB migrations |
| Execution Package Svc | `backend/experiment-service/app/services/execution_package_service.py` | Execution package logic |
| Execution Runtime | `backend/experiment-service/runtime/experiment_runtime.py` | Runtime engine |
| Analytics Service | `backend/experiment-service/analytics/experiment_analytics_service.py` | Analytics logic |

---

## 5. PIHUB Core Components

| Component | Path | Role |
|-----------|------|------|
| PIHUB API Main | `backend/pihub/api/main.py` | Core API entry |
| Cache Manager | `backend/pihub/cache/cache_manager.py` | Cache orchestration |
| Cache Store | `backend/pihub/cache/store.py` | Cache storage backend |
| Active Registry | `backend/pihub/cache/active_registry.py` | Active pack registry |
| Failover | `backend/pihub/cache/failover.py` | Failover logic |
| Debug Routes | `backend/pihub/cache/debug_routes.py` | Debug endpoints |
| Retrieval Optimization | `backend/pihub/cache/retrieval_optimization.py` | Cache retrieval |
| Pack Manager | `backend/pihub/cache/pack_manager.py` | Pack lifecycle |
| Sync Engine | `backend/pihub/sync/sync_engine.py` | Sync orchestration |
| Deployment Startup | `backend/pihub/deployment/startup.py` | Container startup |
| Deployment Validation | `backend/pihub/deployment/validation.py` | Startup validation |
| Deployment Monitoring | `backend/pihub/deployment/monitoring.py` | Monitoring hooks |
| Hotspot Manager | `backend/pihub/deployment/hotspot.py` | Hotspot setup |
| Backend Recovery | `backend/pihub/deployment/backend_recovery.py` | Recovery from failure |
| Monitoring Health | `backend/pihub/monitoring/health.py` | Health checks |
| Network Discovery | `backend/pihub/network/discovery.py` | Device discovery |
| Device Manager | `backend/pihub/devices/manager.py` | Device management |

---

## 6. Inference Service Components

| Component | Path | Role |
|-----------|------|------|
| Main | `backend/inference-service/app/main.py` | AI Tutor service |

---

## 7. Shared Components

| Component | Path | Role |
|-----------|------|------|
| Config | `backend/shared/config.py` | Configuration management |
| Schemas | `backend/shared/schemas.py` | Pydantic shared models |
| Pack Schemas | `backend/shared/pack_schemas.py` | Pack-specific schemas |
| Vector Store | `backend/shared/vector_store.py` | Qdrant client wrapper |
| Curriculum Graph | `backend/shared/curriculum_graph.py` | Shared graph model |
| Text Normalization | `backend/shared/text_normalization.py` | Text normalization |
| Topic Normalization | `backend/shared/topic_normalization.py` | Topic normalization |

---

## 8. Curriculum Builder Components

| Component | Path | Role |
|-----------|------|------|
| Build Subject | `backend/curriculum-builder/build_subject.py` | Build single subject |
| Build Curriculum | `backend/curriculum-builder/build_curriculum.py` | Full curriculum build |
| Complete Curriculum | `backend/curriculum-builder/build_complete_curriculum.py` | End-to-end build |
| Curriculum Scanner | `backend/curriculum-builder/curriculum_scanner.py` | Scan curriculum dirs |
| Enrichment Registry | `backend/curriculum-builder/enrichment_registry.py` | Registry of enrichments |
| Master Pack | `backend/curriculum-builder/master_pack_registry.py` | Master pack registry |
| Folder Parser | `backend/curriculum-builder/folder_parser.py` | Parse curriculum folders |

---

## 9. Content Forensics & Quality Components

| Component | Path | Role |
|-----------|------|------|
| Ground Truth Builder | `backend/content_forensics/ground_truth_builder.py` | Builds ground truth |
| Qdrant Retrieval Audit | `backend/content_forensics/qdrant_retrieval_audit.py` | Audits Qdrant retrieval |
| Deduplication Audit | `backend/content_forensics/deduplication_loss_audit.py` | Checks dedup loss |
| Formula Retention | `backend/content_forensics/formula_retention_audit.py` | Checks formula retention |
| Concept Loss Root Cause | `backend/content_forensics/concept_loss_root_cause.py` | RC analysis |
| Grade 8 Forensics | `backend/content_forensics/run_grade8_forensics.py` | Grade 8-specific |
| Cleanup Loss Audit | `backend/content_forensics/cleanup_loss_audit.py` | Cleanup loss check |
| Flashcard Evaluator | `backend/content_quality/flashcard_evaluator.py` | Evaluates flashcards |
| Quiz Evaluator | `backend/content_quality/quiz_evaluator.py` | Evaluates quizzes |
| Summary Evaluator | `backend/content_quality/summary_evaluator.py` | Evaluates summaries |
| Tutor Evaluator | `backend/content_quality/tutor_evaluator.py` | Evaluates tutor quality |
| Reader Evaluator | `backend/content_quality/reader_evaluator.py` | Evaluates reader quality |

---

## 10. Script Components

| Component | Path | Role |
|-----------|------|------|
| Content Quality Audit | `backend/scripts/content_quality_audit.py` | Quality audit runner |
| Content Extraction Audit | `backend/scripts/content_extraction_audit.py` | Extraction audit |
| Pack Content Quality | `backend/scripts/pack_content_quality_validation.py` | Validates pack content |
| Semantic Pipeline Audit | `backend/scripts/semantic_content_pipeline_audit.py` | Pipeline audit |
| Regenerate Packs | `backend/scripts/regenerate_damaged_packs.py` | Regeneration runner |
| Publish Packs | `backend/scripts/publish_runtime_packs.py` | Publishes to runtime |
| Pack Runtime Inventory | `backend/scripts/pack_runtime_inventory.py` | Inventory runner |
| Retrieval Eval | `backend/scripts/retrieval_evaluation.py` | Retrieval quality eval |
| Performance Benchmark | `backend/scripts/performance_benchmark.py` | Benchmark runner |
| Integration Suite | `backend/scripts/integration_test_suite.py` | Integration tests |
| Full Corpus Regeneration | `backend/scripts/full_corpus_regeneration_api.py` | Full regeneration |
| Full Curriculum API | `backend/scripts/full_curriculum_api_certification.py` | Curriculum cert |
| Textbook Catalog Report | `backend/scripts/textbook_catalog_report.py` | Catalog generation |
| Pack Publication Audit | `backend/scripts/pack_publication_integrity_audit.py` | Integrity audit |
| Selective Pack Sync Audit | `backend/scripts/selective_pack_sync_audit.py` | Sync audit |

---

*End of Backend Component Map*
