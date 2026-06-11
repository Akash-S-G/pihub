# Backend API Map
*Generated: 2026-06-09*

---

## Overview

This document maps all API endpoints, organized by service, with method, path, and tags.

---

## 1. Gateway APIs

| # | Method | Endpoint | Purpose |
|---|--------|----------|---------|
| 1 | GET | `/` | Root health check |
| 2 | GET | `/discovery` | Service discovery |
| 3 | GET | `/discovery/beacon` | Discovery beacon |
| 4 | GET | `/tutor/capabilities` | List AI tutor capabilities |
| 5 | GET | `/health` | Health check |
| 6 | POST | `/content/upload` | Upload educational content |
| 7 | POST | `/upload` | Legacy upload |
| 8 | POST | `/ingest/textbook` | Ingest textbook |
| 9 | POST | `/rag/search` | Semantic search |
| 10 | GET | `/rag/chapter` | Search by chapter |
| 11 | GET | `/rag/subject` | Search by subject |
| 12 | POST | `/ai/chat` | AI chat (tutor) |
| 13 | POST | `/ai/tutor` | AI tutor session |
| 14 | GET | `/ai/health` | AI service health |
| 15 | GET | `/sync` | Sync status |
| 16 | POST | `/sync` | Trigger sync |
| 17 | GET | `/packs` | List packs |
| 18 | GET | `/packs/sync` | Pack sync status |
| 19 | GET | `/packs/catalog` | Pack catalog |
| 20 | GET | `/packs/recommended` | Recommended packs |
| 21 | POST | `/packs/generate` | Generate pack |
| 22 | GET | `/packs/{pack_id}/manifest` | Pack manifest |
| 23 | GET | `/packs/{pack_id}/download` | Download pack |
| 24 | GET | `/api/v1/pdf/catalog` | PDF catalog |
| 25 | GET | `/api/v1/pdf/resolve` | Resolve PDF |
| 26 | GET | `/api/v1/pdf/book/{grade}/{subject}` | PDF by subject |
| 27 | GET | `/api/v1/pdf/chapter/{chapter_id}` | PDF chapter |
| 28 | GET | `/api/v1/pdf/chapter/{chapter_id}/metadata` | Chapter metadata |
| 29 | GET | `/api/v1/pdf/file/{book_id}` | PDF file |
| 30 | GET | `/experiments` | List experiments |
| 31 | GET | `/experiments/catalog` | Experiment catalog |
| 32 | GET | `/experiments/search` | Search experiments |
| 33 | GET | `/experiments/{experiment_id}` | Experiment detail |
| 34 | GET | `/experiments/{experiment_id}/download` | Download experiment |
| 35 | GET | `/experiments/{experiment_id}/certification` | Experiment cert |
| 36 | GET | `/experiment-templates` | List templates |
| 37 | POST | `/experiment-runs` | Start experiment run |
| 38 | GET | `/experiment-runs/{run_id}` | Get run |
| 39 | POST | `/experiment-runs/{run_id}/events` | Submit event |
| 40 | POST | `/experiment-runs/{run_id}/complete` | Complete run |
| 41 | GET | `/analytics/student/{student_id}` | Student analytics |
| 42 | GET | `/analytics/experiment/{experiment_id}` | Experiment analytics |
| 43 | GET | `/analytics/system` | System analytics |
| 44 | GET | `/analytics/top-experiments` | Top experiments |
| 45 | GET | `/flashcards` | List flashcards |
| 46 | GET | `/quizzes` | List quizzes |
| 47 | GET | `/glossary` | List glossary |
| 48 | GET | `/summaries` | List summaries |
| 49 | POST | `/planner/lesson` | Lesson plan |
| 50 | GET | `/metrics/tutor` | Tutor metrics |
| 51 | GET | `/metrics/retrieval` | Retrieval metrics |
| 52 | GET | `/progress/{student_id}` | Student progress |
| 53 | POST | `/progress` | Update progress |
| 54 | GET | `/quiz-sessions` | List quiz sessions |
| 55 | GET | `/quiz-sessions/{quiz_session_id}` | Quiz session detail |
| 56 | POST | `/quiz-sessions/{quiz_session_id}/answer` | Submit answer |
| 57 | GET | `/classroom` | Classroom list |
| 58 | POST | `/classroom` | Create classroom |
| 59 | GET | `/devices` | Device list |
| 60 | POST | `/devices` | Register device |
| 61 | GET | `/debug/curriculum` | Debug curriculum |
| 62 | GET | `/debug/metadata` | Debug metadata |

---

## 2. Pack Service APIs

| # | Method | Endpoint | Tag | Purpose |
|---|--------|----------|-----|---------|
| 1 | GET | `/api/v1/pdf/catalog` | PDF Reader API | List PDF catalog |
| 2 | GET | `/api/v1/pdf/chapter/{chapter_id}` | PDF Reader API | Get chapter PDF |
| 3 | GET | `/api/v1/pdf/chapter/{chapter_id}/metadata` | PDF Reader API | Chapter metadata |
| 4 | GET | `/api/v1/pdf/book/{grade}/{subject}` | PDF Reader API | Get book PDF |
| 5 | GET | `/api/v1/pdf/resolve` | PDF Reader API | Resolve PDF |
| 6 | GET | `/api/v1/pdf/file/{book_id}` | PDF Reader API | Download file |
| 7 | POST | `/api/v1/pdf/scan` | PDF Reader API | Scan PDF |
| 8 | GET | `/packs/list` | Pack API | List packs |
| 9 | GET | `/packs/search` | Pack API | Search packs |
| 10 | GET | `/packs/{pack_id}` | Pack API | Pack detail |
| 11 | GET | `/packs/{pack_id}/manifest` | Pack API | Pack manifest |
| 12 | GET | `/packs/{pack_id}/preview` | Pack API | Pack preview |
| 13 | GET | `/packs/{pack_id}/download` | Pack API | Download pack |
| 14 | POST | `/packs/{pack_id}/validate` | Pack API | Validate pack |
| 15 | POST | `/sync/manifest` | Pack API | Sync manifest |
| 16 | POST | `/sync/delta` | Pack API | Delta sync |
| 17 | GET | `/packs/{pack_id}/benchmark` | Pack API | Benchmark |
| 18 | GET | `/packs/{pack_id}/evaluation` | Pack API | Evaluation |
| 19 | GET | `/debug/packs/{pack_id}` | Internal Debug | Pack debug |
| 20 | GET | `/debug/packs/{pack_id}/validation` | Internal Debug | Validation debug |
| 21 | GET | `/debug/reports/{pack_id}` | Internal Debug | Report debug |

---

## 3. Content Pipeline APIs

| # | Method | Endpoint | Purpose |
|---|--------|----------|---------|
| 1 | GET | `/health` | Health check |
| 2 | POST | `/ingest/pdf` | Ingest PDF |
| 3 | POST | `/ingest/textbook` | Ingest textbook |
| 4 | POST | `/ingest/directory` | Ingest directory |
| 5 | POST | `/rag/search` | RAG search |
| 6 | POST | `/rag/curriculum_search` | Curriculum search |
| 7 | GET | `/rag/chapter` | Search by chapter |
| 8 | GET | `/rag/subject` | Search by subject |
| 9 | GET | `/debug/curriculum` | Debug curriculum |
| 10 | GET | `/debug/curriculum-relations` | Debug relations |
| 11 | GET | `/debug/metadata` | Debug metadata |
| 12 | GET | `/debug/chunks` | Debug chunks |
| 13 | POST | `/debug/retrieval` | Test retrieval |
| 14 | GET | `/debug/similarity` | Debug similarity |
| 15 | GET | `/debug/pack-preview` | Pack preview |
| 16 | GET | `/debug/learning-pack-preview` | Preview learning pack |

---

## 4. Experiment Service APIs

| # | Method | Endpoint | Tag | Purpose |
|---|--------|----------|-----|---------|
| 1 | GET | `/experiments` | Experiment Engine | List experiments |
| 2 | GET | `/experiments/search` | Experiment Engine | Search experiments |
| 3 | GET | `/experiments/subjects` | Experiment Engine | Subjects |
| 4 | GET | `/experiments/topics` | Experiment Engine | Topics |
| 5 | GET | `/experiments/{experiment_id}` | Experiment Engine | Get experiment |
| 6 | GET | `/experiment-templates` | Experiment Engine | Templates |
| 7 | POST | `/experiment-runs` | Experiment Engine | Run experiment |
| 8 | GET | `/experiment-runs/{run_id}` | Experiment Engine | Get run |
| 9 | POST | `/experiment-runs/{run_id}/events` | Experiment Engine | Events |
| 10 | GET | `/experiment-runs/{run_id}/events` | Experiment Engine | Get events |
| 11 | POST | `/experiment-runs/{run_id}/complete` | Experiment Engine | Complete run |
| 12 | GET | `/analytics/student/{student_id}` | Experiment Engine | Student analytics |
| 13 | GET | `/analytics/experiment/{experiment_id}` | Experiment Engine | Experiment analytics |
| 14 | GET | `/analytics/system` | Experiment Engine | System analytics |
| 15 | GET | `/analytics/top-experiments` | Experiment Engine | Top experiments |
| 16 | GET | `/experiment-metrics` | Experiment Engine | Metrics |
| 17 | GET | `/maintenance/database-health` | Experiment Maintenance | DB health |
| 18 | GET | `/maintenance/hash-audit` | Experiment Maintenance | Hash audit |
| 19 | GET | `/maintenance/storage-stats` | Experiment Maintenance | Storage stats |
| 20 | GET | `/maintenance/classroom-health` | Experiment Maintenance | Classroom health |
| 21 | GET | `/maintenance/system-integrity` | Experiment Maintenance | Integrity |
| 22 | POST | `/builder/manifests` | Experiment Builder | Create manifest |
| 23 | GET | `/builder/manifests` | Experiment Builder | List manifests |
| 24 | PUT | `/builder/manifests/{manifest_id}` | Experiment Builder | Update manifest |
| 25 | POST | `/builder/manifests/{manifest_id}/publish` | Experiment Builder | Publish |
| 26 | POST | `/builder/manifests/{manifest_id}/archive` | Experiment Builder | Archive |
| 27 | GET | `/builder/manifests/{manifest_id}` | Experiment Builder | Get manifest |
| 28 | POST | `/classroom/sessions` | Classroom Distribution | Create session |
| 29 | GET | `/classroom/sessions` | Classroom Distribution | List sessions |
| 30 | POST | `/classroom/sessions/{session_id}/assignments` | Classroom Distribution | Assign |
| 31 | GET | `/classroom/sessions/{session_id}/assignments` | Classroom Distribution | Get assignments |
| 32 | POST | `/classroom/assignments/{assignment_id}/submit` | Classroom Distribution | Submit |
| 33 | GET | `/classroom/assignments/{assignment_id}/submissions` | Classroom Distribution | Submissions |
| 34 | GET | `/classroom/analytics` | Classroom Distribution | Analytics |
| 35 | POST | `/ai/generate-experiment` | AI Experiment Authoring | AI generate |
| 36 | POST | `/ai/refine-experiment` | AI Experiment Authoring | AI refine |
| 37 | POST | `/ai/explain-experiment` | AI Experiment Authoring | AI explain |
| 38 | GET | `/experiments/catalog` | Experiment Content | Content catalog |
| 39 | GET | `/experiments/{experiment_id}/download` |聪明, experiment Content | Download |
| 40 | GET | `/experiments/{experiment_id}/certification` | Experiment Content | Certify |
| 41 | GET | `/chapters/{chapter_id}/experiments` | Experiment Content | Chapter experiments |
| 42 | POST | `/sharing/export` | Experiment Sharing | Export |
| 43 | POST | `/sharing/import` | Experiment Sharing | Import |
| 44 | POST | `/sharing/verify` | Experiment Sharing | Verify |
| 45 | POST | `/sharing/sign` | Experiment Sharing | Sign |
| 46 | POST | `/sharing/trust` | Experiment Sharing | Trust |
| 47 | GET | `/sharing/analytics` | Experiment Sharing | Analytics |
|

---

## 5. PIHUB Core APIs

| # | Method | Endpoint | Purpose |
|---|--------|----------|---------|
| 1 | GET | `/health` | Service health |
| 2 | GET | `/classroom` | List classrooms |
| 3 | POST | `/classroom` | Create classroom |
| 4 | GET | `/devices` | List devices |
| 5 | POST | `/devices` | Register device |
| 6 | POST | `/devices/{device_id}/heartbeat` | Device heartbeat |
| 7 | GET | `/packs` | List packs |
| 8 | POST | `/packs` | Create pack |
| 9 | GET | `/packs/{pack_id}` | Pack detail |
| 10 | GET | `/packs/{pack_id}/download` | Download pack |
| 11 | POST | `/sync` | Sync data |
| 12 | GET | `/sync` | Sync status |
| 13 | GET | `/progress/{student_id}` | Student progress |
| 14 | POST | `/progress` | Update progress |
| 15 | GET | `/quiz-sessions` | Quiz sessions |
| 16 | GET | `/sessions/{session_id}` | Session detail |
| 17 | GET | `/network/status` | Network status |
| 18 | POST | `/network/session` | Create session |
| 19 | GET | `/deployment/startup/validate` | Startup validation |
| 20 | GET | `/deployment/status` | Deployment status |
| 21 | GET | `/deployment/hotspot/health` | Hotspot health |
| 22 | POST | `/deployment/hotspot/setup` | Setup hotspot |
| 23 | GET | `/deployment/metrics/classroom` | Classroom metrics |
| 24 | GET | `/deployment/validation/deployment` | Deployment check |

---

## 6. Inference Service APIs

| # | Method | Endpoint | Purpose |
|---|--------|----------|---------|
| 1 | GET | `/ai/health` | Service health |
| 2 | POST | `/ai/chat` | AI chat (general) |
| 3 | POST | `/ai/tutor` | AI tutor (education) |
| 4 | GET | `/metrics/tutor` | Tutor metrics |
| 5 | GET | `/metrics/retrieval` | Retrieval metrics |

---

## 7. Debug & Monitoring APIs

| # | Method | Endpoint | Purpose |
|---|--------|----------|---------|
| 1 | GET | `/debug/packs` | Debug packs |
| 2 | GET | `/debug/cache` | Debug cache |
| 3 | GET | `/debug/retrieval` | Debug retrieval |
| 4 | GET | `/debug/host-status` | Debug failover |
| 5 | GET | `/debug/sync` | Debug sync |
| 6 | GET | `/debug/system` | Debug system |
| 7 | GET | `/debug/active-packs` | Active packs |
| 8 | GET | `/debug/metrics` | Debug metrics |
| 9 | GET | `/cache/stats` | Cache stats |
| 10 | GET | `/cache/health` | Cache health |
| 11 | GET | `/health` | Health check |
| 12 | GET | `/health/resources` | Health resources |
| 13 | GET | `/health/diagnostics` | Health diagnostics |

---

## API Summary by Service

| Service | Total Endpoints |
|---------|----------------|
| Gateway | 65 |
| Pack Service | 21 |
| Content Pipeline | 16 |
| Experiment Service | 47 |
| PIHUB Core | 24 |
| Inference Service | 5 |
| **TOTAL** | **178** |

---

*End of Backend API Map*
