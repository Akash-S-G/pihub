# PIHUB Backend - Component Architecture & Extension Guide

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          CLIENT/FRONTEND LAYER                          │
└────────────────┬────────────────────────┬──────────────────┬────────────┘
                 │                        │                  │
         ┌───────▼────────┐   ┌──────────▼─────────┐  ┌─────▼──────────┐
         │  Content        │   │  Pack              │  │ Inference      │
         │  Pipeline       │   │  Service           │  │ Service        │
         │  (8001)         │   │  (8030)            │  │ (8010)         │
         └───────┬────────┘   └──────────┬─────────┘  └─────┬──────────┘
                 │                       │                  │
    ┌────────────┴────────────┬──────────┴──────────┐      │
    │                         │                     │      │
    ▼                         ▼                     ▼      ▼
┌─────────────────────────────────────────────────────────────────┐
│              Qdrant Vector Store (6333)                         │
│              Collection: educational_chunks                    │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Points: {vector, payload{text, metadata}}               │  │
│  │ Index: COSINE distance, 384-dimensional vectors       │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
    ▲                                              │
    │                                              │
    └──────────────────────────────────────────────┘
```

---

## Service Communication Diagram

```
CLIENT
  │
  ├─→ POST /ingest/pdf ──────────────────┐
  │                                       │
  │   Content Pipeline                   │
  │   ┌──────────────────────────────┐   │
  │   │ 1. Extract text              │   │
  │   │ 2. Parse sections            │   │
  │   │ 3. Chunk (180-1300 chars)    │   │
  │   │ 4. Build metadata            │   │
  │   │ 5. Generate embeddings       │   │
  │   │ 6. Upsert to Qdrant          │   │
  │   └──────────────────────────────┘   │
  │                 │                    │
  │                 ▼                    │
  │            Qdrant (6333)             │
  │         educational_chunks           │
  │                                       │
  ├─→ POST /rag/search ──────────────────┤
  │                                       │
  │   1. Curriculum inference            │
  │   2. Query encoding                  │
  │   3. Qdrant search + filter         │
  │   4. Hybrid reranking               │
  │   5. Score filtering (>0.25)        │
  │   6. Return top-K                   │
  │                                       │
  ├─→ POST /packs/generate ──────────────┤
  │      (via pack-service)              │
  │                                       │
  │   Pack Service                       │
  │   ┌──────────────────────────────┐   │
  │   │ 1. Query Qdrant for chunks   │   │
  │   │ 2. Retrieve embeddings       │   │
  │   │ 3. Generate artifacts:      │   │
  │   │    - Summaries              │   │
  │   │    - Glossary               │   │
  │   │    - Quizzes                │   │
  │   │    - Flashcards             │   │
  │   │    - Enrichment resources   │   │
  │   │ 4. Build manifest           │   │
  │   │ 5. Create ZIP archive       │   │
  │   │ 6. Store in repository      │   │
  │   └──────────────────────────────┘   │
  │                                       │
  └───────────────────────────────────────┘
```

---

## Component Deep Dives

### 1. CONTENT PIPELINE ARCHITECTURE

#### Module Dependency Tree

```
Main Pipeline (app/main.py)
├── TextbookIngester
│   └── MetadataExtractor
│
├── EducationalChunkerV2
│   ├── SectionParser
│   ├── ParagraphMerger
│   ├── EducationalClassifier
│   ├── FormulaPreserver
│   ├── ConceptBoundaryDetector
│   └── ChunkMetadataBuilder
│
├── EducationalRetrievalEngine
│   ├── _semantic_score()
│   ├── _lexical_score()
│   ├── _chunk_type_score()
│   ├── _topic_scores()
│   └── rank()
│
├── Educational Intelligence
│   ├── SummaryGenerator
│   ├── GlossaryExtractor
│   ├── QuizGenerator
│   │   └── GlossaryExtractor (dependency)
│   ├── FlashcardGenerator
│   ├── EnrichmentRouter
│   │   ├── CurriculumEnrichmentMatcher
│   │   ├── SimulationFinder
│   │   ├── ExperimentRetriever
│   │   └── EducationalFilter
│   ├── QualityEvaluator
│   └── PackCompiler
│
├── CurriculumGraph
│   ├── load() - Load from JSON
│   ├── infer_subjects_for_query()
│   ├── infer_topics_for_query()
│   ├── infer_concepts_for_text()
│   └── save() - Save to JSON
│
└── Vector Store (shared)
    ├── make_qdrant_client()
    ├── ensure_collection()
    ├── upsert_chunks()
    └── build_filter()
```

#### Flow Diagram: Processing a PDF

```
PDF Upload
    ↓
file_path = upload_dir / filename
    ↓
Extract Metadata from filename/path
    {
        "grade": extracted_grade,
        "subject": extracted_subject,
        "chapter": extracted_chapter,
        "language": detected_language
    }
    ↓
Extract Text from PDF
    text = PyPDF2 or similar
    ↓
Section Parsing
    sections = [
        {title: "Chapter 1", content: "..."},
        {title: "Section 1.1", content: "..."}
    ]
    ↓
Paragraph Merging (merge if < 120 chars)
    merged_paragraphs = [
        "Paragraph 1 content...",
        "Merged paragraph 2-3..."
    ]
    ↓
Chunking (180-1300 chars)
    FOR EACH paragraph:
        IF is_formula or is_boundary:
            CREATE atomic chunk
        ELSE IF accumulated_length > max:
            FLUSH current chunk
            START new chunk
        ELSE
            ADD to current chunk
    ↓
    Chunks generated:
    [{
        text: "Photosynthesis is...",
        metadata: {
            grade: 7,
            subject: "Science",
            chapter: "Nutrition",
            chunk_type: "definition",
            keywords: ["photo", "synthesis", ...]
        }
    }, ...]
    ↓
Embedding Generation
    FOR EACH chunk.text:
        embedding = SimpleEmbeddingModel.encode(text)
        → 384-dimensional vector
    ↓
Qdrant Upsert
    FOR EACH chunk:
        point_id = uuid.uuid4()
        upsert_chunks(
            embeddings=[embedding],
            texts=[chunk.text],
            metadatas=[chunk.metadata]
        )
    ↓
Response
    IngestResponse {
        file_name: "textbook.pdf",
        chunks_created: 245,
        collection: "educational_chunks",
        metadata: {...}
    }
```

---

### 2. RETRIEVAL ENGINE ARCHITECTURE

#### Scoring Breakdown

```
Query: "What is photosynthesis?"

Step 1: Curriculum Inference
├─ infer_subject("What is...") → "Science"
├─ infer_topics("What is...") → ["photosynthesis", "chlorophyll"]
├─ prerequisites["photosynthesis"] → ["cell_structure", "sunlight"]
└─ related["photosynthesis"] → ["respiration", "glucose"]

Step 2: Query Encoding
├─ tokenize("what is photosynthesis") → {what, is, photosynthesis}
├─ for token in tokens:
│   hash_value = Blake2b(token)
│   index = hash_value % 384
│   vector[index] += 1.0
└─ normalize(vector) → embedding ∈ R^384

Step 3: Qdrant Search with Filter
├─ query_vector = embedding
├─ filter = build_filter({grade: 7, subject: "Science"})
├─ limit = 20
└─ results = [
    {id: "chunk_001", score: 0.78, payload: {...}},
    {id: "chunk_002", score: 0.65, payload: {...}},
    ...
  ]

Step 4: Hybrid Reranking
FOR each result in results:
    
    payload = result.payload
    
    A. SEMANTIC SCORE (vector similarity)
       semantic = clamp(0, 1, result.score)
    
    B. LEXICAL SCORE (token overlap)
       query_tokens = {what, is, photosynthesis}
       payload_text = text + subject + chapter + topics + concepts
       payload_tokens = tokenize(payload_text)
       lexical = |overlap| / max(|query|, 1)
    
    C. CHUNK TYPE SCORE
       IF "define" in query AND chunk_type == "definition":
           chunk_type_score = 1.0
       ELSE IF "formula" in query AND chunk_type == "formula":
           chunk_type_score = 1.0
       ELSE IF "example" in query AND chunk_type == "example":
           chunk_type_score = 0.9
       ELSE IF chunk_type in {definition, explanation, qa}:
           chunk_type_score = 0.6
       ELSE:
           chunk_type_score = 0.3
    
    D. TOPIC SCORE
       IF chunk_topics ∩ inferred_topics:
           topic_score = 1.0
       ELSE IF chunk_topics ∩ prerequisites:
           topic_score = 0.75
       ELSE IF chunk_topics ∩ related:
           topic_score = 0.6
       ELSE:
           topic_score = 0.0
    
    E. SUBJECT MATCH
       subject_match = 1.0 IF chunk.subject == target_subject ELSE 0.0
    
    F. CHAPTER MATCH
       IF chunk.chapter == target_chapter:
           chapter_match = 1.0
       ELSE IF query_tokens contain chapter words:
           chapter_match = 0.6
       ELSE:
           chapter_match = 0.0
    
    G. EDUCATIONAL SCORE
       educational = (
           0.40 * topic_score +
           0.20 * chapter_match +
           0.15 * subject_match +
           0.25 * chunk_type_score
       )
    
    H. FINAL SCORE
       final_score = (
           0.45 * semantic +
           0.25 * lexical +
           0.30 * educational
       )
    
    scored_results.append({
        id: result.id,
        score: final_score,
        text: payload.text,
        ranking_debug: {
            semantic, lexical, educational,
            topic_band, subject_match, chapter_match,
            chunk_type_score
        }
    })

Step 5: Post-Processing
├─ FILTER: Drop score < 0.25
├─ SORT: By score descending
└─ TRUNCATE: Top 5 results

Result:
[
  {
    id: "chunk_001",
    score: 0.892,
    text: "Photosynthesis is the process by which plants...",
    metadata: {...},
    ranking_debug: {
      semantic: 0.85,
      lexical: 0.9,
      educational: 0.88,
      topic_band: "exact_topic",
      subject_match: 1.0,
      chapter_match: 0.6,
      chunk_type_score: 0.9
    }
  },
  ...
]
```

---

### 3. PACK SERVICE ARCHITECTURE

#### Pack Generation Pipeline

```
User Request: generate_class_pack(grade=7, subject="Science", ...)

PHASE 1: Query Qdrant
├─ conditions = [
│   {key: "grade", match: {value: 7}},
│   {key: "subject", match: {value: "Science"}},
│   {key: "language", match: {value: "english"}}
│ ]
├─ chunks = qdrant.search(
│   filter=build_filter(conditions),
│   limit=10000
│ )
└─ Result: ~2000 chunks for class 7 Science

PHASE 2: Compile Artifacts
├─ SUMMARIES
│   FOR EACH chapter:
│       chunks_per_chapter = filter(chunks, chapter=ch)
│       summary = SummaryGenerator.generate(chunks_per_chapter)
│       summaries.append(summary)
│
├─ GLOSSARY
│   glossary = GlossaryExtractor.extract(chunks)
│   deduplicate by term
│
├─ QUIZZES
│   quizzes = QuizGenerator.generate(chunks, limit=100)
│   MCQ, T/F, Fill-blank questions
│
├─ FLASHCARDS
│   flashcards = FlashcardGenerator.generate(glossary)
│   front/back pairs from glossary terms
│
├─ ENRICHMENT
│   FOR EACH unique topic in chunks:
│       enrichment += EnrichmentRouter.route(topic)
│       simulations, experiments, diagrams
│
└─ RETRIEVAL INDEX
    index = {
        "topics": [...],
        "chapters": [...],
        "metadata_filters": [...]
    }

PHASE 3: Build Manifest
├─ manifest = {
│   pack_id: "class7_science_english",
│   version: "1.0.0",
│   grade: 7,
│   subject: "Science",
│   language: "english",
│   chunk_count: 2145,
│   summary_count: 12,
│   glossary_count: 342,
│   quiz_count: 450,
│   flashcard_count: 342,
│   enrichment_count: 85,
│   created_at: "2026-05-18T...",
│   checksum: "sha256_hash",
│   compressed_size_mb: 45.2,
│   quality_scores: {
│       completeness: 0.95,
│       relevance: 0.92,
│       accuracy: 0.94
│   }
│ }
│
└─ artifacts = {
    "content.json": [...chunks],
    "summaries.json": [...summaries],
    "glossary.json": [...glossary_entries],
    "quizzes.json": [...quizzes],
    "flashcards.json": [...flashcards],
    "enrichment.json": {...enrichment},
    "metadata.json": manifest
  }

PHASE 4: Store & Archive
├─ pack_dir = /shared/packs/class7_science_english/
├─ FOR EACH (filename, content) in artifacts:
│   write(pack_dir / filename, json.dumps(content))
│
├─ archive_path = pack_dir.tar.gz
├─ create_archive(pack_dir)
│
├─ Registry.register(manifest, pack_dir, archive_path)
│
└─ Response: {
    pack_id: "class7_science_english",
    version: "1.0.0",
    status: "completed",
    download_url: "/packs/class7_science_english/download",
    manifest_url: "/packs/class7_science_english/manifest"
  }
```

#### Pack Storage Structure

```
/shared/packs/
├── class7_science_english/
│   ├── manifest.json
│   │   {
│   │       pack_id, version, grade, subject, language,
│   │       chunk_count, summary_count, ...,
│   │       quality_scores, checksum
│   │   }
│   │
│   ├── content.json
│   │   [
│   │       {
│   │           text: "...",
│   │           metadata: {grade, subject, chapter, ...}
│   │       },
│   │       ...
│   │   ]
│   │
│   ├── glossary.json
│   │   [
│   │       {term, definition, chapter, subject},
│   │       ...
│   │   ]
│   │
│   ├── quizzes.json
│   │   [
│   │       {
│   │           question_type: "mcq|true_false|fill_blank",
│   │           question: "...",
│   │           options: [...],
│   │           answer: "..."
│   │       },
│   │       ...
│   │   ]
│   │
│   ├── flashcards.json
│   │   [
│   │       {front: "term", back: "definition"},
│   │       ...
│   │   ]
│   │
│   ├── summaries.json
│   │   [
│   │       {
│   │           chapter: "...",
│   │           topic: "...",
│   │           summary: "...",
│   │           key_points: [...],
│   │           revision_notes: [...]
│   │       },
│   │       ...
│   │   ]
│   │
│   ├── enrichment.json
│   │   {
│   │       topic: {
│   │           sources: [...],
│   │           resources: [{type, title, ...}, ...]
│   │       },
│   │       ...
│   │   }
│   │
│   └── retrieval_index/
│       └── index.json
│           {topics, chapters, metadata_filters}
│
├── class7_science_english.tar.gz
│   (compressed archive)
│
└── class7_science_english_registry.json
    {pack metadata, version history}
```

---

## Extension Points

### Adding a New Content Type

**Example**: Add support for video transcripts

```python
# Step 1: Create new ingestor in content-pipeline/app/

from app.content_pipeline import BaseIngestor

class VideoTranscriptIngestor(BaseIngestor):
    """Process video transcript files."""
    
    async def ingest(self, file_path: Path, metadata: dict) -> list[dict]:
        # Read transcript
        transcript = self._read_transcript(file_path)
        
        # Chunk by timestamps
        chunks = self._chunk_by_timestamp(transcript)
        
        # Classify chunk types
        for chunk in chunks:
            chunk["metadata"]["chunk_type"] = self._classify_video_segment(chunk)
        
        return chunks

# Step 2: Register in Pipeline.main

# In app/main.py
self.video_ingestor = VideoTranscriptIngestor()

@app.post("/ingest/video-transcript")
async def ingest_video_transcript(file: UploadFile, ...):
    chunks = await pipeline.video_ingestor.ingest(file_path, metadata)
    # ... rest of ingestion
```

---

### Improving Retrieval Ranking

**Example**: Add semantic field matching

```python
# Modify EducationalRetrievalEngine in retrieval_engine.py

class EducationalRetrievalEngine:
    def rank(self, query: str, hits, limit: int, ...):
        # ... existing code ...
        
        for hit in hits:
            # ... existing scores ...
            
            # NEW: Field-specific semantic matching
            field_score = self._field_semantic_score(query, hit.payload)
            
            # Adjust weights
            educational = (
                0.35 * topic_score +      # reduced from 0.40
                0.20 * chapter_match +
                0.15 * subject_match +
                0.25 * chunk_type_score +
                0.05 * field_score        # NEW
            )
            
            final_score = 0.45 * semantic + 0.25 * lexical + 0.30 * educational
    
    def _field_semantic_score(self, query: str, payload: dict) -> float:
        """Match query to specific metadata fields."""
        # High score if query matches chapter/topic directly
        query_l = query.lower()
        chapter = str(payload.get("chapter", "")).lower()
        topic = str(payload.get("topic", "")).lower()
        
        if query_l in chapter or chapter in query_l:
            return 0.8
        if query_l in topic or topic in query_l:
            return 0.7
        return 0.0
```

---

### Adding Custom Artifact Generator

**Example**: Add "Learning Path" generator

```python
# Create new file: content-pipeline/app/educational_intelligence/
# learning_path_generator.py

class LearningPathGenerator:
    """Generate recommended learning sequences."""
    
    def generate(self, chunks: list[dict], student_level: int = 5) -> list[dict]:
        """
        Create structured learning path from chunks.
        
        Args:
            chunks: List of content chunks
            student_level: 1-10 difficulty (default 5=middle)
        
        Returns:
            Ordered sequence with prerequisites and checkpoints
        """
        # Group by concept
        concepts = self._group_by_concept(chunks)
        
        # Build dependency graph
        graph = self._build_concept_graph(concepts)
        
        # Generate path
        paths = []
        for concept in concepts:
            path = self._topological_sort(graph, start=concept)
            paths.append({
                "concept": concept,
                "steps": path,
                "estimated_duration_minutes": len(path) * 15,
                "checkpoints": [
                    {"step": 3, "type": "quiz"},
                    {"step": 7, "type": "practice"},
                    {"step": 10, "type": "project"}
                ]
            })
        
        return paths

# Register in content-pipeline/app/main.py
from app.educational_intelligence.learning_path_generator import LearningPathGenerator

class Pipeline:
    def __init__(self):
        # ... existing ...
        self.learning_path_generator = LearningPathGenerator()

# Add API endpoint
@app.get("/artifacts/learning-paths")
async def get_learning_paths(query: str, limit: int = 5):
    chunks = await pipeline.search(query, limit=20)
    paths = pipeline.learning_path_generator.generate(chunks)
    return {"paths": paths[:limit]}
```

---

### Custom Quality Metrics

**Example**: Add linguistic complexity scoring

```python
# Create: pack-service/app/evaluation/linguistic_quality.py

class LinguisticQualityScorer:
    """Score content by linguistic complexity."""
    
    def score(self, artifacts: dict) -> dict:
        """
        Calculate linguistic metrics.
        
        Metrics:
        - Flesch Reading Ease (0-100, higher = easier)
        - Technical term density
        - Sentence complexity
        - Vocabulary diversity
        """
        from textstat import flesch_reading_ease
        
        all_text = " ".join([
            chunk["text"] for chunk in artifacts.get("content", [])
        ])
        
        return {
            "flesch_ease": flesch_reading_ease(all_text),
            "technical_density": self._technical_term_density(all_text),
            "avg_sentence_length": self._avg_sentence_length(all_text),
            "vocabulary_diversity": self._vocabulary_diversity(all_text)
        }
    
    # Helper methods...
```

---

## Data Migration & Backup

### Backup Qdrant Collection

```python
# Script: backend/scripts/backup_qdrant.py

import json
from pathlib import Path
from qdrant_client import QdrantClient

def backup_collection(qdrant_url: str, collection_name: str, 
                     output_dir: Path):
    """Backup entire collection to JSON."""
    client = QdrantClient(url=qdrant_url)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    collection_info = client.get_collection(collection_name)
    points_count = collection_info.points_count
    
    # Fetch all points in batches
    all_points = []
    batch_size = 1000
    
    for offset in range(0, points_count, batch_size):
        points = client.scroll(
            collection_name=collection_name,
            limit=batch_size,
            offset=offset
        )[0]
        
        for point in points:
            all_points.append({
                "id": point.id,
                "vector": point.vector,
                "payload": point.payload
            })
    
    # Save to file
    backup_path = output_dir / f"{collection_name}_backup.json"
    backup_path.write_text(
        json.dumps(all_points, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    
    print(f"Backed up {points_count} points to {backup_path}")
```

---

## Testing Utilities

### Search Testing

```python
# Test: content-pipeline/tests/test_retrieval_ranking.py

import pytest
from app.retrieval_engine.educational_retrieval_engine import EducationalRetrievalEngine

@pytest.fixture
def retrieval_engine():
    return EducationalRetrievalEngine()

def test_definition_query_ranks_definition_chunks_high(retrieval_engine):
    """Definition queries should prefer definition chunks."""
    
    hit_definition = MockHit(
        id="def_1",
        score=0.5,
        payload={"text": "Photosynthesis is...", "chunk_type": "definition"}
    )
    hit_example = MockHit(
        id="ex_1",
        score=0.5,
        payload={"text": "Example of photosynthesis...", "chunk_type": "example"}
    )
    
    ranked = retrieval_engine.rank(
        query="what is photosynthesis",
        hits=[hit_definition, hit_example],
        limit=2,
        routed_filters={},
        inferred_subject="Biology",
        inferred_topics=["photosynthesis"],
        prerequisite_topics=[],
        related_topics=[]
    )
    
    # Definition should rank higher
    assert ranked[0]["id"] == "def_1"
    assert ranked[0]["score"] > ranked[1]["score"]
```

---

## Performance Tuning Parameters

### Chunk Size Optimization

```python
# Current settings in educational_chunker.py
min_chunk_chars = 180      # Minimum chunk size
max_chunk_chars = 1300     # Maximum chunk size

# Tuning recommendations:
# - Decrease min for denser retrieval (more results)
# - Increase max for better context preservation
# - Sweet spot: 200-1500 chars for educational content
```

### Embedding Dimension Trade-offs

```python
# Current: 384 dimensions (SimpleEmbeddingModel)

# Trade-offs:
# 384 dims: Balance (default)
#   Storage: ~384 * 4 bytes ≈ 1.5 KB per chunk
#   Search speed: Baseline
#
# 768 dims: Higher quality
#   Storage: ~3 KB per chunk (2x)
#   Search speed: ~1.5x slower
#
# 256 dims: Faster, lossy
#   Storage: ~1 KB per chunk (0.67x)
#   Search speed: ~1.5x faster
#   Quality: ~5-10% lower
```

### Reranking Weights Tuning

```python
# In EducationalRetrievalEngine.rank()

# Current weights:
semantic_weight = 0.45      # Vector similarity
lexical_weight = 0.25       # Token overlap
educational_weight = 0.30   # Curriculum alignment

# Tuning scenarios:
# High semantic accuracy (math/science):
semantic_weight = 0.50
lexical_weight = 0.20
educational_weight = 0.30

# High curriculum alignment (language arts):
semantic_weight = 0.30
lexical_weight = 0.20
educational_weight = 0.50

# Balanced (default):
semantic_weight = 0.45
lexical_weight = 0.25
educational_weight = 0.30
```

---

## Integration Checklist for New Features

- [ ] Create module in appropriate service (content-pipeline, pack-service, etc.)
- [ ] Add request/response models to shared/schemas.py
- [ ] Create API endpoint in app/main.py or app/api/
- [ ] Add unit tests in tests/ folder
- [ ] Update configuration in shared/config.py if needed
- [ ] Document in API docstrings (FastAPI auto-docs)
- [ ] Add integration test with Qdrant
- [ ] Update this architecture document
- [ ] Test with sample data end-to-end
- [ ] Benchmark performance impact
- [ ] Add error handling and logging

---

**Architecture Document Version**: 2.0  
**Last Updated**: May 18, 2026
