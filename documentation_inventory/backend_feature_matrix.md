# Backend Feature Matrix
*Generated: 2026-06-09*

---

## Overview

This matrix cross-references platform features with backend service capabilities.

---

## Feature × Service Matrix

| # | Feature | Gateway | Content Pipeline | Pack Service | Experiment Service | Inference Service | PIHUB Core |
|---|---------|---------|-----------------|-------------|-------------------|-------------------|-----------|
| 1 | **PDF/Textbook Upload** | W (proxy) | W (own) | - | - | - | - |
| 2 | **Document Chunking** | - | W (own) | - | - | - | - |
| 3 | **Vector Embedding** | - | W (own) | - | - | - | - |
| 4 | **Semantic Search (RAG)** | R (proxy) | W (own) | - | - | - | - |
| 5 | **Curriculum Graph** | - | W (own) | - | - | - | - |
| 6 | **Flashcard Generation** | - | W (own) | - | - | - | - |
| 7 | **Quiz Generation** | - | W (own) | - | - | - | - |
| 8 | **Summary Generation** | - | W (own) | - | - | - | - |
| 9 | **Glossary Extraction** | - | W (own) | - | - | - | - |
| 10 | **Multilingual (Kannada)** | - | W (own) | - | - | - | - |
| 11 | **Pack Compilation** | - | - | W (own) | - | - | - |
| 12 | **Pack Manifest Validation** | - | - | W (own) | - | - | - |
| 13 | **Pack Download** | W (proxy) | - | W (own) | - | - | - |
| 14 | **Pack Sync (Delta)** | W (proxy) | - | W (own) | - | - | - |
| 15 | **PDF Reader / Catalog** | W (proxy) | - | W (own) | - | - | - |
| 16 | **Textbook Builder** | - | - | W (own) | - | - | - |
| 17 | **Worked Example Builder** | - | - | W (own) | - | - | - |
| 18 | **Experiment Catalog** | W (proxy) | - | - | W (own) | - | - |
| 19 | **Experiment Run** | W (proxy) | - | - | W (own) | - | - |
| 20 | **Experiment Builder** | W (proxy) | - | - | W (own) | - | - |
| 21 | **AI Experiment Generation** | - | - | - | W (own) | - | - |
| 22 | **Classroom Sessions** | W (proxy) | - | - | W (own) | - | - |
| 23 | **Experiment Analytics** | W (proxy) | - | - | W (own) | - | - |
| 24 | **AI Chat (Tutor)** | W (proxy) | - | - | - | W (own) | - |
| 25 | **AI Health Check** | W (proxy) | - | - | - | W (own) | - |
| 26 | **Device Discovery** | W (proxy) | - | - | - | - | W (own) |
| 27 | **Hotspot Management** | W (proxy) | - | - | - | - | W (own) |
| 28 | **Cache Management** | W (proxy) | - | - | - | - | W (own) |
| 29 | **Sync Engine** | W (proxy) | - | - | - | - | W (own) |
| 30 | **Deployment Health** | W (proxy) | - | - | - | - | W (own) |

W = Write / Own | R = Read / Use | - = Not applicable

---

## Feature × Data Store Matrix

| # | Feature | Qdrant | SQLite | Shared Local/FS |
|---|---------|--------|--------|-----------------|
| 1 | PDF Chunk Indexing | W | - | - |
| 2 | Semantic Search | R | - | - |
| 3 | Curriculum Graph Nodes | - | - | W |
| 4 | Concept Links | - | - | W |
| 5 | Experiment Manifests | - | W | - |
| 6 | Classroom Sessions | - | W | - |
| 7 | Experiment Sharing | - | W | - |
| 8 | Builder Manifests | - | W | - |
| 9 | Pack Files (.otpack) | - | - | W |
| 10 | Seed Experiments | - | - | W |
| 11 | Analytics Data | - | W | - |
| 12 | Sync Delta Cache | - | - | W |

---

## Capability Cross-Reference

| Capability | Services Involved | Data Stores |
|-----------|-------------------|-------------|
| **Content Ingestion** | content-pipeline | Qdrant, local FS |
| **RAG / Search** | content-pipeline, inference-service | Qdrant |
| **Pack Generation** | content-pipeline, pack-service | local FS |
| **Pack Distribution** | gateway, pack-service, pihub | local FS, Qdrant |
| **Experiment Management** | experiment-service | SQLite |
| **AI Tutor** | gateway, inference-service | Qdrant |
| **Device Ecosystem** | pihub | local FS |
| **Curriculum** | content-pipeline, curriculum-builder | local FS |
| **Forensics** | content-forensics, scripts | Qdrant, local FS |
| **Quality** | content-quality | local FS |

---

*End of Backend Feature Matrix*
