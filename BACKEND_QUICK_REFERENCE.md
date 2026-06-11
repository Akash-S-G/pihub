# PIHUB Backend - Quick Reference Guide

## Core API Endpoints by Service

### Content Pipeline (8001)

```bash
# Ingestion
POST /ingest/pdf
  - file: UploadFile
  - grade: int (optional)
  - subject: str (optional)
  - chapter: str (optional)
  - language: str (optional)
  → Response: IngestResponse {file_name, chunks_created, collection, metadata}

POST /ingest/textbook
  - file: UploadFile
  - grade: int (optional)
  - subject: str (optional)
  - chapter: str (optional)
  → Response: Same as PDF

POST /ingest/directory
  - directory: str
  - recursive: bool = True
  - source: str (optional)
  → Response: {status, files_processed, chunks_created}

# Retrieval (RAG)
POST /rag/search
  Body: {
    "query": "What is photosynthesis?",
    "limit": 5,
    "metadata": {"grade": 7, "subject": "Biology"}
  }
  → Response: SearchResponse {query, results: [ChunkResult]}

GET /rag/chapter?chapter=Photosynthesis&limit=5
  → Response: SearchResponse

GET /rag/subject?subject=Biology&limit=5
  → Response: SearchResponse

# Debug
GET /health
  → Response: {status, service, checks}

GET /debug/curriculum
  → Response: Full curriculum graph

GET /debug/curriculum-relations
  → Response: Topic relation graph

GET /debug/metadata
  → Response: Metadata structure schema
```

---

### Pack Service (8030)

```bash
# Pack Generation
POST /packs/generate
  Body: PackGenerationRequest {
    "pack_type": "class",  # or "chapter", "language"
    "grade": 7,
    "subject": "Science",
    "language": "english",
    "compression": "gzip",
    "include_media": false
  }
  → Response: PackGenerationResponse {pack_id, status, chunk_count, download_url}

# Pack Management
GET /packs/list
  → Response: {packs: [PackListItem], total_count}

GET /packs/search?grade=7&subject=Science&language=english
  → Response: {packs: [PackListItem], total_count}

GET /packs/{pack_id}
  → Response: PackListItem (metadata only)

GET /packs/{pack_id}/manifest
  → Response: PackManifest {metadata, chunks, media_files, checksum}

GET /packs/{pack_id}/preview
  → Response: PackPreviewResponse {
      manifest, summaries, glossary, quizzes, 
      flashcards, enrichment, quality_scores
    }

GET /packs/{pack_id}/download
  → Response: File download (application/octet-stream)

POST /packs/{pack_id}/validate
  → Response: PackValidationReport {valid, errors, warnings}

# Sync
POST /sync/manifest
  Query: host_version=1.0.0
  → Response: Sync manifest for distribution
```

---

### Inference Service (8010)

```bash
POST /chat
  Body: {
    "question": "Explain photosynthesis",
    "grade": 7,
    "subject": "Biology",
    "limit": 5,
    "stream": false
  }
  → Response: InferenceResponse {answer, model, context}

POST /tutor
  Body: TutorRequest {
    ...ChatRequest,
    "hint_style": "guided"  # or "socratic"
  }
  → Response: InferenceResponse

GET /health
  → Response: {status, service, checks}
```

---

## Key Python Classes & Methods

### Content Pipeline

```python
# Main Pipeline
from app.main import Pipeline

pipeline = Pipeline()

# Ingestion
chunks = await pipeline._ingest_file(
    file_path=Path("textbook.pdf"),
    metadata={"grade": 7, "subject": "Science"}
)

# Search
results = await pipeline.search(
    query="photosynthesis",
    limit=5,
    metadata=Metadata(grade=7, subject="Science")
)

# Retrieval Engine
from app.retrieval_engine.educational_retrieval_engine import EducationalRetrievalEngine

engine = EducationalRetrievalEngine()
ranked = engine.rank(
    query="photosynthesis",
    hits=raw_results,
    limit=5,
    routed_filters={"subject": "Science"},
    inferred_subject="Biology",
    inferred_topics=["photosynthesis", "chlorophyll"],
    prerequisite_topics=["cell_structure"],
    related_topics=["respiration"]
)

# Educational Chunking
from app.content_pipeline.educational_chunker import EducationalChunkerV2

chunker = EducationalChunkerV2(min_chunk_chars=180, max_chunk_chars=1300)
chunks = chunker.chunk_educational(
    text="...",
    metadata={"grade": 7, "subject": "Science"}
)

# Metadata Building
from app.content_pipeline.chunk_metadata_builder import ChunkMetadataBuilder

builder = ChunkMetadataBuilder()
metadata = builder.build(
    text="Photosynthesis is...",
    base_metadata={"grade": 7, "subject": "Science"},
    section_title="Chapter 5: Nutrition",
    chunk_type="definition",
    topic_hint="Photosynthesis"
)

# Intelligence Modules
from app.educational_intelligence import (
    QuizGenerator, SummaryGenerator, GlossaryExtractor,
    FlashcardGenerator, EnrichmentRouter, PackCompiler
)

quiz_gen = QuizGenerator()
quizzes = quiz_gen.generate(chunks, limit=8)

summary_gen = SummaryGenerator()
summary = summary_gen.generate(chunks, chapter="5", topic="Photosynthesis")

glossary_ext = GlossaryExtractor()
glossary = glossary_ext.extract(chunks)

enrichment_router = EnrichmentRouter()
enrichment = enrichment_router.route(
    topic="Photosynthesis",
    grade=7,
    subject="Science"
)

pack_compiler = PackCompiler()
manifest = pack_compiler.compile(
    pack_name="Science Grade 7 - Nutrition",
    chunks=chunks,
    summaries=summary,
    glossary=glossary,
    quizzes=quizzes,
    flashcards=flashcards,
    enrichment=enrichment,
    output_dir=Path("/shared/packs")
)
```

### Pack Service

```python
from app.pack_generator import PackGenerator
from app.pack_storage.pack_repository import PackRepository
from app.validation.pack_validator import PackValidator

# Generator
generator = PackGenerator(
    qdrant_url="http://qdrant:6333",
    qdrant_collection="educational_chunks",
    pack_storage_path="/shared/packs",
    curriculum_graph_path="/shared/curriculum_graph.json"
)

# Generate class pack
pack_id = await generator.generate_class_pack(
    grade=7,
    subject="Science",
    language="english",
    compression="gzip"
)

# Generate chapter pack
chapter_pack_id = await generator.generate_chapter_pack(
    grade=7,
    subject="Science",
    chapter="Photosynthesis",
    compression="gzip"
)

# Repository
repository = PackRepository(storage_root=Path("/shared/packs"))

# Save pack
record = repository.save_pack({
    "pack_id": "class7_science",
    "grade": 7,
    "subject": "Science",
    "language": "english",
    "artifacts": {...},
    "generation_metadata": {...}
})

# List packs
packs = repository.list_packs()

# Get pack
pack = repository.get_pack("class7_science", version="1.0.0")

# Load manifest
manifest = repository.load_manifest("class7_science")

# Search packs
matching = repository.search(grade=7, subject="Science")

# Validate
valid, errors = repository.validate_pack("class7_science")

# Validator
validator = PackValidator()

result = validator.validate(
    manifest=manifest,
    artifacts=artifacts,
    quality_scores=quality_scores
)

if result.valid:
    print("Pack is valid")
else:
    print(f"Errors: {result.errors}")
```

### Vector Store Operations

```python
from shared.vector_store import (
    make_qdrant_client, ensure_collection,
    upsert_chunks, build_filter
)
from qdrant_client.http import models as qmodels

# Initialize
client = make_qdrant_client("http://qdrant:6333")

# Ensure collection exists
ensure_collection(
    client=client,
    collection_name="educational_chunks",
    vector_size=384
)

# Insert chunks
chunk_ids = upsert_chunks(
    client=client,
    collection_name="educational_chunks",
    embeddings=[
        [0.1, 0.2, 0.3, ...],  # 384-dim vectors
        [0.2, 0.3, 0.4, ...],
    ],
    texts=[
        "Photosynthesis is...",
        "Chlorophyll is...",
    ],
    metadatas=[
        {
            "grade": 7,
            "subject": "Science",
            "chapter": "Nutrition",
            "topic": "Photosynthesis",
            "chunk_type": "definition"
        },
        {...}
    ]
)

# Search with filter
filter_obj = build_filter({
    "grade": 7,
    "subject": "Science"
})

results = client.search(
    collection_name="educational_chunks",
    query_vector=[0.1, 0.2, ...],  # Encoded query
    query_filter=filter_obj,
    limit=10,
    score_threshold=0.1
)

for result in results:
    print(f"ID: {result.id}")
    print(f"Score: {result.score}")
    print(f"Text: {result.payload['text']}")
    print(f"Metadata: {result.payload}")
```

---

## Data Flow Diagrams

### Complete Ingestion + Pack Generation Flow

```
User Upload (PDF/Textbook)
        ↓
    File Validation
        ↓
    Text Extraction
        ↓
    Metadata Extraction (from filename/content)
        ↓
    Paragraph Merging (min 120 chars)
        ↓
    Semantic Chunking (180-1300 chars)
        ├─ Section detection
        ├─ Concept boundary detection
        ├─ Formula preservation
        └─ Chunk type classification
        ↓
    Metadata Enrichment
        ├─ Keywords extraction (TF-based)
        ├─ Difficulty inference (grade-based)
        ├─ Topic assignment
        └─ Language detection
        ↓
    Embedding Generation (SimpleEmbeddingModel)
        ├─ Tokenization
        ├─ Hash-based encoding
        └─ L2 normalization
        ↓
    Qdrant Upsert
        ├─ Create collection if needed
        ├─ Insert points with embeddings
        └─ Store metadata as payload
        ↓
    Pack Service Query
        ├─ Filter by grade/subject/chapter
        ├─ Retrieve all matching chunks
        └─ Get embeddings + metadata
        ↓
    Artifact Generation
        ├─ Summaries (SummaryGenerator)
        ├─ Glossary (GlossaryExtractor)
        ├─ Quizzes (QuizGenerator)
        ├─ Flashcards (FlashcardGenerator)
        └─ Enrichment (EnrichmentRouter)
        ↓
    Manifest Compilation
        ├─ Build PackManifest
        ├─ Calculate checksums
        ├─ Create artifacts JSON files
        └─ Generate ZIP archive
        ↓
    Repository Storage
        ├─ Save to /shared/packs/{pack_id}/
        ├─ Register in PackRegistry
        └─ Return pack metadata
        ↓
    User Download
        └─ Download compressed pack
```

---

### Query Retrieval + Ranking Flow

```
User Query
    ↓
Curriculum Inference
    ├─ Infer subject from query
    ├─ Infer topics from query  
    ├─ Get prerequisite topics
    └─ Get related topics
    ↓
Query Encoding
    └─ SimpleEmbeddingModel.encode(query)
        → 384-dim vector
    ↓
Qdrant Search
    ├─ Build metadata filter (grade, subject, chapter, language)
    ├─ Search with vector + filter
    └─ Return top 20 candidates
    ↓
Hybrid Reranking (for each result)
    ├─ Semantic Score = vector_similarity (0-1)
    │
    ├─ Lexical Score = token_overlap / max_tokens
    │
    ├─ Chunk Type Score
    │   ├─ "define" query + definition chunk = 1.0
    │   ├─ "formula" query + formula chunk = 1.0
    │   ├─ "example" query + example chunk = 0.9
    │   └─ Explanation chunks = 0.6
    │
    ├─ Topic Score
    │   ├─ Exact match = 1.0
    │   ├─ Prerequisite = 0.75
    │   ├─ Related = 0.6
    │   └─ None = 0.0
    │
    ├─ Subject Match = 1.0 if exact, 0.0 otherwise
    │
    ├─ Chapter Match
    │   ├─ Exact = 1.0
    │   ├─ Contains query token = 0.6
    │   └─ None = 0.0
    │
    └─ Final Score = 
        0.45 * semantic +
        0.25 * lexical +
        0.30 * (
            0.40 * topic +
            0.20 * chapter +
            0.15 * subject +
            0.25 * chunk_type
        )
    ↓
Post-Processing
    ├─ Drop score < 0.25
    ├─ Sort descending
    └─ Truncate to limit
    ↓
Response
    └─ Return ranked results with debug info
```

---

## Common Queries & Solutions

### Q: How do I add support for a new language?

**A**: 
1. Update `ENABLE_AUTO_INGESTION` to ingest new language textbooks
2. Add language code to `Metadata.language` field
3. Update `MultilingualSupport.detect_language()` in educational_intelligence
4. Generate language-specific pack: `generator.generate_language_pack(language="hindi")`

### Q: How do I improve retrieval quality?

**A**:
1. Adjust weights in `EducationalRetrievalEngine.rank()`:
   - Increase `semantic_weight` for stronger embedding matching
   - Increase `educational_weight` for curriculum alignment
2. Tune minimum score threshold (currently 0.25)
3. Add more topic/prerequisite knowledge to curriculum graph
4. Switch to production embedding model (from SimpleEmbeddingModel)

### Q: How do I reduce pack size?

**A**:
1. Use `compression="zstd"` instead of "gzip"
2. Enable `quantize_embeddings=True` when generating
3. Reduce chunk count by filtering (grade-specific packs instead of class packs)
4. Exclude media with `include_media=False`

### Q: How do I debug a failed retrieval?

**A**:
1. Use `GET /debug/curriculum` to verify curriculum graph is loaded
2. Use `POST /rag/search` with `include_debug=true` to get ranking breakdown
3. Check Qdrant collection: `GET /health` (includes Qdrant status)
4. Verify metadata in chunks: `GET /debug/metadata`

### Q: How do I validate a pack after generation?

**A**:
```python
# Via API
POST /packs/{pack_id}/validate

# Checks performed:
# - Manifest structure
# - All artifacts present
# - Chunk references valid
# - Glossary term uniqueness
# - Quiz question/answer pairs
# - Quality score ranges
```

---

## Environment Variables

```bash
# Service URLs
QDRANT_URL=http://qdrant:6333
QDRANT_COLLECTION=educational_chunks
CONTENT_PIPELINE_URL=http://content-pipeline:8001
PACK_SERVICE_URL=http://pack-service:8030
INFERENCE_SERVICE_URL=http://inference-service:8010

# Storage Paths
UPLOAD_DIR=/shared/uploads
WORK_DIR=/shared/work
CONTENT_DIR=/shared/content
CURRICULUM_GRAPH_PATH=/shared/work/curriculum_graph.json
PACK_STORAGE_PATH=/shared/packs

# Features
ENABLE_AUTO_INGESTION=false
ENABLE_SEMANTIC_EDUCATIONAL_CHUNKING=true
ENABLE_CURRICULUM_GRAPH_ENGINE=true
ENABLE_EDUCATIONAL_RETRIEVAL_ENGINE=true

# Inference
LLAMA_SERVER_HOST=127.0.0.1
LLAMA_SERVER_PORT=8081
LLAMA_MODEL_PATH=/models/model.gguf
LLAMA_CONTEXT_SIZE=2048
LLAMA_MAX_TOKENS=256

# Logging
LOG_LEVEL=INFO
```

---

## Database Schema Overview

### Qdrant Collection: `educational_chunks`

**Vector Config**:
- Size: 384 dimensions
- Distance: COSINE

**Point Payload (Metadata)**:
```json
{
  "text": "Photosynthesis is the process...",
  "grade": 7,
  "subject": "Science",
  "chapter": "Nutrition",
  "section": "Section 5.1",
  "topic": "Photosynthesis",
  "chunk_type": "definition",
  "language": "english",
  "difficulty": "grade_7",
  "keywords": ["photosynthesis", "chlorophyll", "sunlight"],
  "source": "NCERT Science Textbook",
  "topics": ["Photosynthesis", "Chlorophyll"],
  "concepts": ["Light reactions", "Dark reactions"]
}
```

---

## Performance Benchmarks

| Operation | Typical Time | Notes |
|-----------|--------------|-------|
| PDF ingestion (10 pages) | 5-10 sec | Includes chunking + embedding |
| Qdrant search | 50-100 ms | With metadata filter |
| Hybrid reranking (top 20) | 10-20 ms | All scoring calculations |
| Pack generation (7000 chunks) | 2-5 min | Includes artifact generation |
| Pack download (50 MB) | 10-30 sec | Network dependent |

---

## Troubleshooting Checklist

- [ ] Qdrant is running: `docker ps | grep qdrant`
- [ ] Collection exists: Check Qdrant dashboard
- [ ] Curriculum graph loaded: `GET /debug/curriculum`
- [ ] Embeddings generated: Verify vector size matches
- [ ] Metadata fields populated: `GET /debug/metadata`
- [ ] Search results ranked: Check `ranking_debug` in response
- [ ] Pack artifacts complete: `POST /packs/{pack_id}/validate`
- [ ] Storage paths exist: `/shared/uploads`, `/shared/packs`, etc.

---

**Quick Reference Version**: 1.0  
**Last Updated**: May 18, 2026
