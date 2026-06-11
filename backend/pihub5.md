
## Curriculum-Aware Educational Content Infrastructure

---

# CURRENT PROJECT STATUS

## Backend Infrastructure Status

| Component | Status |
|---|---|
| Docker Multi-Service Architecture | ✅ Working |
| Gateway Service | ✅ Working |
| NGINX Reverse Proxy | ✅ Working |
| Qdrant Vector Database | ✅ Working |
| Inference Service | ✅ Working |
| Phi-2 Local Inference | ✅ Working |
| Content Pipeline | ✅ Basic Working |
| RAG Retrieval | ✅ Basic Working |
| Upload Pipeline | ✅ Working |
| AI Chat Endpoint | ✅ Working |
| Tutor Endpoint | ✅ Working |
| Concurrent Requests | ✅ Stable on Phi-2 |

---

# CURRENT LIMITATIONS

## RAG Problems

Current RAG issues:

- Irrelevant chunks injected
- No similarity threshold filtering
- No curriculum-aware retrieval
- No chapter-aware chunking
- No educational metadata
- No structured textbook ingestion
- No multilingual retrieval
- No educational enrichment engine
- No offline educational packs

---

# PHASE 3 GOAL

Transform the system from:

```text
Generic Local RAG Chatbot
````

into:

```text
Offline Curriculum-Aware Educational AI Infrastructure
```

---

# CORE ARCHITECTURE VISION

```text
Textbooks
↓
Content Pipeline
↓
Curriculum Graph
↓
Educational Enrichment
↓
Embeddings + Metadata
↓
Qdrant Vector DB
↓
Offline Educational Packs
↓
PiHub Classroom Distribution
↓
Offline AI Tutoring
```

---

# IMPLEMENTATION ROADMAP

# STEP 1 — FIX CURRENT RAG QUALITY

## PRIORITY: CRITICAL

---

## 1A — Retrieval Score Filtering

### Problem

Current retrieval injects irrelevant chunks with:

```json
"score": 0.0
```

### Fix

Inside content-pipeline:

```python
results = [r for r in results if r.score > 0.3]
```

---

## 1B — Limit Retrieval Count

### Current Problem

Too many unrelated chunks injected.

### Fix

```python
top_k = 1
```

---

## 1C — Skip RAG if No Relevant Context

### Fix

```python
if len(results) == 0:
    use_rag = False
```

---

## 1D — Output Cleanup

Remove Phi-2 special tokens:

```text
<|im_end|>
<|im_start|>
```

### Postprocess

```python
answer = answer.replace("<|im_end|>", "")
```

---

# STEP 2 — STRUCTURED TEXTBOOK INGESTION

## PRIORITY: CRITICAL

---

# Directory Structure

```text
content/
 ├── class_6/
 │    ├── science/
 │    ├── maths/
 │    └── social/
 ├── class_7/
 ├── class_8/
 ├── class_9/
 └── class_10/
```

---

## 2A — PDF Extraction

### Libraries

| Library       | Purpose              |
| ------------- | -------------------- |
| PyMuPDF       | PDF text extraction  |
| Tesseract OCR | Scanned textbook OCR |

---

## 2B — Metadata Extraction

Extract automatically:

```json
{
  "grade": 6,
  "subject": "science",
  "language": "english"
}
```

---

## 2C — Chapter Detection

Detect headings like:

```text
Chapter 1
Nutrition in Plants
```

Store metadata:

```json
{
  "chapter": "Nutrition in Plants"
}
```

---

## 2D — Semantic Chunking

DO NOT use fixed-size chunks.

### Correct Strategy

```text
Chapter
↓
Section
↓
Paragraph
```

---

# STEP 3 — AUTO INGESTION ENGINE

## PRIORITY: HIGH

---

# Goal

Teacher drops PDF into folder.

Pipeline automatically:

```text
Detect PDF
↓
Extract Text
↓
Chunk
↓
Generate Embeddings
↓
Store in Qdrant
```

---

## 3A — File Watcher

### Use

| Library  | Purpose           |
| -------- | ----------------- |
| watchdog | Monitor new files |

---

# STEP 4 — CURRICULUM GRAPH

## PRIORITY: HIGH

---

# Goal

Build educational hierarchy:

```text
Grade
↓
Subject
↓
Chapter
↓
Topic
↓
Concept
```

---

# Example

```json
{
  "grade": 7,
  "subject": "science",
  "chapter": "Nutrition in Plants",
  "topics": [
    "photosynthesis",
    "chlorophyll",
    "leaf structure"
  ]
}
```

---

# STEP 5 — EDUCATIONAL ENRICHMENT ENGINE

## PRIORITY: HIGH

---

# IMPORTANT DESIGN PRINCIPLE

DO NOT perform random internet scraping.

ONLY perform:

```text
Topic-Guided Educational Enrichment
```

---

# Example

From textbook topic:

```text
Photosynthesis
```

Generate enrichment searches:

| Type                | Query                                   |
| ------------------- | --------------------------------------- |
| Experiments         | photosynthesis experiment middle school |
| Simulations         | photosynthesis virtual lab              |
| Animations          | photosynthesis educational animation    |
| Real-world examples | photosynthesis farming example          |
| Diagrams            | chloroplast diagram middle school       |

---

# Trusted Sources Only

| Source          | Purpose                 |
| --------------- | ----------------------- |
| NCERT           | Curriculum              |
| Khan Academy    | Explanations            |
| PhET            | Simulations             |
| OLabs           | Virtual labs            |
| GeoGebra        | Mathematics             |
| NASA Education  | Science                 |
| Britannica Kids | Simplified explanations |

---

# STEP 6 — EDUCATIONAL FILTERING

## PRIORITY: HIGH

---

# Use LLM to Validate Content

For every discovered resource:

Evaluate:

| Check                | Purpose                |
| -------------------- | ---------------------- |
| Syllabus aligned?    | Curriculum correctness |
| Age appropriate?     | Grade suitability      |
| Educational quality? | Content usefulness     |
| Too advanced?        | Filtering              |
| Offline usable?      | Classroom deployment   |

---

# STEP 7 — MEDIA / SIMULATION PIPELINE

## PRIORITY: MEDIUM

---

# Future Educational Media Types

| Type                        | Use                    |
| --------------------------- | ---------------------- |
| Simulations                 | Virtual labs           |
| GIFs                        | Lightweight animations |
| Diagrams                    | Visual explanations    |
| Interactive HTML            | Offline learning       |
| Audio explanations          | Accessibility          |
| Educational videos metadata | Teacher mode           |

---

# Store Media Metadata

Example:

```json
{
  "type": "simulation",
  "topic": "photosynthesis",
  "offline_supported": true,
  "interactive": true
}
```

---

# STEP 8 — OFFLINE EDUCATIONAL PACKS

## PRIORITY: HIGH

---

# Goal

Generate distributable classroom packs.

---

# Example Pack

```text
class7_science.pack
```

Contains:

| Component              | Included |
| ---------------------- | -------- |
| Textbook chunks        | ✅        |
| Embeddings             | ✅        |
| Metadata               | ✅        |
| Simulations            | ✅        |
| Experiments            | ✅        |
| Diagrams               | ✅        |
| Quizzes                | ✅        |
| Educational enrichment | ✅        |

---

# Pack Structure

```text
pack/
 ├── manifest.json
 ├── vectors.json
 ├── metadata.json
 ├── media/
 ├── quizzes/
 └── textbooks/
```

---

# STEP 9 — MULTILINGUAL PIPELINE

## PRIORITY: MEDIUM

---

# Current Situation

English works reasonably well.

Kannada retrieval currently weak.

---

# Future Improvements

## Multilingual Embeddings

Future models:

| Model              | Purpose               |
| ------------------ | --------------------- |
| bge-m3             | Multilingual          |
| multilingual-e5    | Multilingual          |
| jina-embeddings-v3 | Advanced multilingual |

---

# STEP 10 — APP INTEGRATION

## PRIORITY: HIGH

---

# Required Fixes

## 10A — Remove Hardcoded Ports

App should only know:

```text
http://<backend-ip>
```

NOT:

```text
:8000
```

---

## 10B — Fix Request Schemas

Correct request:

```json
{
  "question": "..."
}
```

---

## 10C — Add Streaming Support

Future real-time token streaming.

---

## 10D — Educational UI Cards

Future UI support for:

* simulations
* experiments
* animations
* diagrams
* quizzes

---

# STEP 11 — GPU ACCELERATION

## PRIORITY: FUTURE

---

# Hardware

RTX 3050 4GB available.

---

# Future Plan

Move from CPU-only inference to:

```text
CUDA llama.cpp
```

Benefits:

* faster inference
* larger models
* multimodal models
* better concurrency

---

# STEP 12 — FUTURE MULTIMODAL SYSTEM

## PRIORITY: FUTURE

---

# Future Features

| Feature                | Goal                    |
| ---------------------- | ----------------------- |
| Image understanding    | Diagram tutoring        |
| Audio explanations     | Accessibility           |
| Simulation interaction | Virtual labs            |
| Animation playback     | Visual learning         |
| Teacher dashboard      | Classroom orchestration |
| Adaptive tutoring      | Personalized learning   |

---

# CURRENT PRIORITIES (NEXT 7 DAYS)

| Priority | Task                             |
| -------- | -------------------------------- |
| 1        | Fix RAG filtering                |
| 2        | Structured textbook ingestion    |
| 3        | Chapter-aware chunking           |
| 4        | Metadata extraction              |
| 5        | Auto PDF ingestion               |
| 6        | Curriculum graph                 |
| 7        | Educational enrichment prototype |

---

# FINAL SYSTEM VISION

The system evolves into:

```text
Offline Distributed Curriculum-Aware Educational Operating System
```

NOT merely:

```text
Local AI Chatbot
```

---

# CORE DIFFERENTIATOR

The real innovation is:

```text
Curriculum-Aware Offline Educational Knowledge Infrastructure
```

combined with:

* local AI inference
* offline classroom distribution
* educational enrichment
* simulations
* curriculum graphs
* offline learning packs
* distributed PiHub deployment

---

```
```
