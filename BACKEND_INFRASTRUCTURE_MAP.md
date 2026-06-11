# PIHUB Backend Infrastructure Map

## Executive Summary

The PIHUB backend is a distributed microservices architecture for educational content processing, compilation, and retrieval. It has four main components:

1. **content-pipeline** (Port 8001): Content ingestion, chunking, retrieval, and pack generation
2. **pack-service** (Port 8030): Pack compilation, storage, validation, and distribution
3. **inference-service** (Port 8010): LLM-based text generation (summaries, quizzes, etc.)
4. **Qdrant Vector Store** (Port 6333): Semantic search via vector embeddings

---

## 1. CONTENT-PIPELINE SERVICE

**Location**: `/home/akash/Desktop/PIHUB/backend/content-pipeline`  
**Port**: 8001  
**Framework**: FastAPI

### 1.1 Entry Point: Main Application
**File**: `app/main.py` (750+ lines)

#### Core Pipeline Class
```python
class Pipeline:
    def __init__(self):
        self.client = make_qdrant_client(settings.qdrant_url)
        self.embedding_model = SimpleEmbeddingModel(dimension=384)
        self.collection_name = settings.qdrant_collection
        self.upload_dir = Path(settings.upload_dir)
        self.work_dir = Path(settings.work_dir)
        self.content_dir = Path(settings.content_dir)
        self.curriculum_graph = CurriculumGraph.load(...)
        self.textbook_ingestor = StructuredTextbookIngest()
        self.retrieval_engine = EducationalRetrievalEngine()
        self.summary_generator = SummaryGenerator()
        self.glossary_extractor = GlossaryExtractor()
        self.quiz_generator = QuizGenerator()
        self.flashcard_generator = FlashcardGenerator()
        self.enrichment_router = EnrichmentRouter()
        self.pack_compiler = PackCompiler()
        self.quality_evaluator = QualityEvaluator()
```

#### Key Capabilities
- PDF extraction and text processing
- Semantic educational chunking
- Qdrant vector indexing
- Curriculum-aware retrieval
- Educational artifact generation
- Pack compilation

#### API Endpoints
- `GET /health` - Health check with detailed service status
- `POST /ingest/pdf` - Upload and process PDF files
- `POST /ingest/textbook` - Structured textbook ingestion
- `POST /ingest/directory` - Batch ingest directory
- `POST /rag/search` - Semantic search queries
- `GET /rag/chapter` - Search by chapter
- `GET /rag/subject` - Search by subject
- `GET /debug/curriculum` - View curriculum graph
- `GET /debug/curriculum-relations` - View relation graph
- `GET /debug/metadata` - View metadata structure

---

### 1.2 Content Pipeline Modules

#### A. Semantic Educational Chunking
**File**: `app/content_pipeline/educational_chunker.py`

```python
class EducationalChunkerV2:
    def __init__(self, min_chunk_chars=180, max_chunk_chars=1300)
    
    def chunk_educational(text: str, metadata: dict) -> list[dict]:
        # Returns list of chunks with metadata
```

**Process**:
1. Parse text into sections using SectionParser
2. Merge paragraphs into coherent blocks
3. Classify chunk types (definition, formula, example, experiment, qa, explanation)
4. Detect concept boundaries
5. Preserve formulas and pedagogical blocks
6. Build normalized metadata for each chunk

**Chunk Types**:
- `definition` - Key term definitions
- `formula` - Mathematical/scientific formulas
- `example` - Worked examples
- `experiment` - Lab procedures/experiments
- `qa` - Question-answer pairs
- `explanation` - Conceptual explanations

**Key Dependencies**:
- `SectionParser` - Identifies sections by headings
- `ParagraphMerger` - Combines small paragraphs (min 120 chars)
- `EducationalClassifier` - Classifies chunk type
- `FormulaPreserver` - Preserves formulas as atomic blocks
- `ConceptBoundaryDetector` - Detects concept shifts
- `ChunkMetadataBuilder` - Builds rich metadata

---

#### B. Chunk Metadata Builder
**File**: `app/content_pipeline/chunk_metadata_builder.py`

```python
class ChunkMetadataBuilder:
    def build(text: str, base_metadata: dict, section_title: str, 
              chunk_type: str, topic_hint: str = None) -> dict:
```

**Metadata Fields**:
- `grade` (int) - Educational grade level
- `subject` (str) - Subject name
- `chapter` (str) - Chapter number/name
- `section` (str) - Section heading
- `topic` (str) - Topic/subtopic
- `chunk_type` (str) - Content classification
- `language` (str) - Language code
- `difficulty` (str) - Inferred difficulty (grade-based)
- `keywords` (list[str]) - Top 8 keywords (stopwords filtered)

**Keyword Extraction**: Uses TF-like approach with stopword filtering

---

#### C. Educational Content Pipeline Components

| Component | File | Purpose |
|-----------|------|---------|
| SectionParser | `section_parser.py` | Identifies hierarchical sections |
| ParagraphMerger | `paragraph_merger.py` | Merges related paragraphs |
| FormulaPreserver | `formula_preserver.py` | Preserves formulas as units |
| ConceptBoundaryDetector | `concept_boundary_detector.py` | Detects topic shifts |
| EducationalClassifier | `educational_classifier.py` | Classifies content type |

---

### 1.3 Retrieval Engine

**File**: `app/retrieval_engine/educational_retrieval_engine.py`

```python
class EducationalRetrievalEngine:
    def rank(query: str, hits: list, limit: int, 
             routed_filters: dict, inferred_subject: str,
             inferred_topics: list, prerequisite_topics: list,
             related_topics: list) -> list[dict]:
```

#### Hybrid Ranking System (45% semantic + 25% lexical + 30% educational)

**Semantic Score** (0-1): Vector similarity from Qdrant
```python
def _semantic_score(raw_score: float) -> float:
    return max(0.0, min(1.0, float(raw_score)))
```

**Lexical Score**: Token overlap between query and chunk
```python
query_tokens = tokenize(query)
payload_tokens = tokenize(chunk_text + metadata)
lexical_score = len(overlap) / max(len(query_tokens), 1)
```

**Educational Score** (40% topic + 20% chapter + 15% subject + 25% chunk_type):

1. **Topic Matching**:
   - Exact topic match: 1.0
   - Prerequisite topic: 0.75
   - Related topic: 0.6
   - No match: 0.0

2. **Chapter Matching**:
   - Exact match: 1.0
   - Contains query tokens: 0.6
   - No match: 0.0

3. **Subject Matching**:
   - Exact match: 1.0
   - No match: 0.0

4. **Chunk Type Matching**:
   - Query = "define" → definition chunk: 1.0
   - Query = "formula" → formula chunk: 1.0
   - Query = "example" → example chunk: 0.9
   - Explanation-type chunks: 0.6
   - Other: 0.3

**Filtering**: Results with final_score < 0.25 are dropped

---

### 1.4 Ingestion Services

#### Textbook Ingestion
**File**: `app/textbook_ingest.py`

- Structured PDF/text processing
- Metadata extraction from filenames and content
- Section and chapter detection
- Handles multi-language detection

#### Auto Ingestion
**File**: `app/auto_ingest.py`

- Monitors content directory for new files
- Automatic processing on addition
- Optional feature (configurable via `ENABLE_AUTO_INGESTION`)

---

## 2. EDUCATIONAL INTELLIGENCE MODULES

**Location**: `/home/akash/Desktop/PIHUB/backend/content-pipeline/app/educational_intelligence`

These modules generate educational artifacts from content chunks:

### 2.1 Quiz Generator
**File**: `educational_intelligence/quiz_generator.py`

```python
class QuizGenerator:
    def generate(chunks: list[dict], limit: int = 8) -> list[dict]:
```

**Output Format**:
```python
{
    "question_type": "mcq|true_false|fill_blank",
    "question": str,
    "options": [str],  # For MCQ
    "answer": str,
    "chapter": str,
    "subject": str
}
```

**Strategy**:
1. Extract glossary terms from chunks
2. Generate 3 question types per term (MCQ, T/F, fill-blank)
3. Build distractors from other glossary terms
4. Returns limit × 3 questions

---

### 2.2 Summary Generator
**File**: `educational_intelligence/summary_generator.py`

```python
class SummaryGenerator:
    def generate(chunks: list[dict], chapter: str = None, 
                 topic: str = None) -> dict:
    
    def quick_review(chunks: list[dict]) -> dict:
```

**Output Format**:
```python
{
    "chapter": str,
    "topic": str,
    "language": str,
    "summary": str,           # First 4 sentences
    "key_points": [str],      # Top 8 focus terms
    "revision_notes": [str],  # "Remember:" prefixed
    "chunk_count": int
}
```

**Strategy**:
1. Collect focus text (definitions, formulas, examples first)
2. Extract first 4 sentences as summary
3. Gather topic/concept keywords
4. Generate revision notes

---

### 2.3 Glossary Extractor
**File**: `educational_intelligence/glossary_extractor.py`

```python
class GlossaryExtractor:
    def extract(chunks: list[dict]) -> list[dict]:
```

**Output Format**:
```python
{
    "term": str,
    "definition": str,
    "chapter": str,
    "subject": str,
    "language": str
}
```

---

### 2.4 Flashcard Generator
**File**: `educational_intelligence/flashcard_generator.py`

Generates front/back flashcard pairs from glossary entries.

---

### 2.5 Enrichment Router
**File**: `educational_intelligence/enrichment_router.py`

```python
class EnrichmentRouter:
    def route(topic: str, grade: int = None, 
              subject: str = None) -> dict:
```

**Output Format**:
```python
{
    "topic": str,
    "grade": int,
    "subject": str,
    "sources": [str],  # NCERT, Khan Academy, PhET, etc.
    "resources": [
        {
            "resource_type": "diagram|simulation|experiment",
            "title": str,
            "offline_supported": bool,
            "interactive": bool,
            "source": str,
            "grade_range": [int]
        }
    ]
}
```

**Strategy**:
1. Match topic to standard enrichment sources
2. Find related simulations and experiments
3. Filter by offline support and grade level
4. Return curated resources

---

### 2.6 Quality Evaluator
**File**: `educational_intelligence/quality_evaluator.py`

Scores generated artifacts:
- Completeness
- Relevance
- Accuracy metrics
- Content quality

---

### 2.7 Pack Compiler
**File**: `educational_intelligence/pack_compiler.py`

```python
class PackCompiler:
    def compile(pack_name: str, chunks: list[dict], 
                summaries: list[dict], glossary: list[dict],
                quizzes: list[dict], flashcards: list[dict],
                enrichment: list[dict], 
                output_dir: Path = None) -> dict:
```

**Artifacts Generated**:
- `content.json` - Chunks with text and metadata
- `summaries.json` - Chapter/topic summaries
- `glossary.json` - Term definitions
- `quizzes.json` - Quiz questions
- `flashcards.json` - Flashcard pairs
- `enrichment.json` - Resource recommendations
- `metadata.json` - Pack manifest
- `.zip` - Compressed archive

---

## 3. PACK-SERVICE

**Location**: `/home/akash/Desktop/PIHUB/backend/pack-service`  
**Port**: 8030  
**Framework**: FastAPI

### 3.1 Pack Generator
**File**: `app/pack_generator.py` (350+ lines)

```python
class PackGenerator:
    def __init__(qdrant_url, qdrant_collection, pack_storage_path,
                 curriculum_graph_path):
        self.client = QdrantClient(url=qdrant_url)
        self.repository = PackRepository(pack_storage_path)
        self.active_generations = {}
```

#### Pack Generation Methods

1. **Class Packs**
```python
async def generate_class_pack(grade: int, subject: str, 
                              language: str = "english",
                              include_media: bool = False,
                              compression: str = "gzip",
                              quantize_embeddings: bool = False) -> str:
```
- Aggregates all chunks for a grade/subject/language
- Compresses into single distributable pack

2. **Chapter Packs**
```python
async def generate_chapter_pack(grade: int, subject: str, chapter: str,
                                language: str, ...) -> str:
```
- Focused pack for single chapter

3. **Language Packs**
```python
async def generate_language_pack(language: str, grade: int = None,
                                 subject: str = None, ...) -> str:
```
- Language-specific aggregation

#### Internal Methods

```python
async def _search_chunks_by_metadata(
    grade: int = None,
    subject: str = None,
    chapter: str = None,
    language: str = None,
    limit: int = 10000
) -> List[dict]:
    # Search Qdrant with metadata filters
    # Returns: List of {chunk_id, text, embedding, metadata, score}
```

**Filter Building**: Uses Qdrant `FieldCondition` for exact matching on:
- grade
- subject
- chapter
- language

---

### 3.2 Pack Storage & Repository
**File**: `app/pack_storage/pack_repository.py`

```python
class PackRepository:
    def __init__(storage_root: Path, 
                 retrieval_index_version: str = "v2"):
        self.locator = PackLocator(storage_root)
        self.registry = PackRegistry(storage_root)
        self.manifest_builder = ManifestBuilder(...)
        self.manifest_validator = ManifestValidator()
```

#### Key Methods

```python
def save_pack(pack_data: dict) -> dict[str, Any]:
    # Saves pack with manifest, artifacts, and archive
    # Returns: {pack_id, version, pack_dir, archive_path, manifest_path, valid}

def list_packs() -> list[dict]:
    # Returns all stored packs with metadata

def get_pack(pack_id: str, version: str = None) -> dict:
    # Retrieves pack record

def load_manifest(pack_id: str, version: str = None) -> dict:
    # Loads pack manifest JSON

def search(**criteria) -> list[dict]:
    # Search packs by grade, subject, chapter, language

def validate_pack(pack_id: str, version: str = None) -> tuple[bool, list[str]]:
    # Validates manifest integrity
```

#### Storage Structure
```
/shared/packs/
├── class7_science/
│   ├── manifest.json
│   ├── content.json
│   ├── glossary.json
│   ├── quizzes.json
│   ├── flashcards.json
│   ├── summaries.json
│   ├── enrichment.json
│   └── retrieval_index/
│       └── index.json
├── class7_science.tar.gz
└── (other packs...)
```

---

### 3.3 Pack Validation
**File**: `app/validation/pack_validator.py`

```python
class PackValidator:
    def __init__(self):
        self.manifest_validator = ManifestValidator()
        self.retrieval_validator = RetrievalValidator()
        self.glossary_validator = GlossaryValidator()
        self.quiz_validator = QuizValidator()
        self.quality_validator = EducationalQualityValidator()
    
    def validate(manifest: dict, artifacts: dict,
                 quality_scores: dict = None) -> PackValidationResult:
```

**Validation Layers**:
1. **Manifest Validation**: Pack ID, version, required fields
2. **Retrieval Validation**: Index integrity, chunk references
3. **Glossary Validation**: Term uniqueness, definition quality
4. **Quiz Validation**: Question/answer pairs, distractors
5. **Quality Validation**: Completeness, score ranges

---

### 3.4 Pack API Routes
**File**: `app/api/pack_routes.py`

#### Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/packs/list` | List all packs |
| GET | `/packs/search` | Search by grade/subject/chapter/language |
| GET | `/packs/{pack_id}` | Get pack metadata |
| GET | `/packs/{pack_id}/manifest` | Get full manifest |
| GET | `/packs/{pack_id}/preview` | Get preview with all artifacts |
| GET | `/packs/{pack_id}/download` | Download compressed pack |
| POST | `/packs/{pack_id}/validate` | Validate pack integrity |
| POST | `/sync/manifest` | Build sync manifest for distribution |

#### Pack Preview Response
```python
{
    "manifest": {...},
    "summaries": [...],
    "glossary": [...],
    "quizzes": [...],
    "flashcards": [...],
    "enrichment": {...},
    "quality_scores": {
        "completeness": 0.92,
        "relevance": 0.88,
        "accuracy": 0.95
    }
}
```

---

### 3.5 Pack Quality Scoring
**File**: `app/evaluation/quality_scoring.py`

```python
class QualityScorer:
    def score(manifest: dict, artifacts: dict):
        # Returns quality metrics
```

**Metrics**:
- `completeness` - Pack has all expected artifacts
- `relevance` - Content matches curriculum
- `accuracy` - Metadata consistency
- `coverage` - Chunk density for topic

---

## 4. INFERENCE SERVICE

**Location**: `/home/akash/Desktop/PIHUB/backend/inference-service`  
**Port**: 8010  
**Framework**: FastAPI

### 4.1 Main Application
**File**: `app/main.py` (250+ lines)

```python
class ModelManager:
    def __init__(settings: Settings):
        self.settings = settings
        self.model_path = Path(settings.llama_model_path)
        self.http = httpx.AsyncClient(timeout=180.0)
        self.prompt_cache = PromptCache(max_size=128)
        
    async def health() -> dict:
        # Checks Llama server status
        
    def start_server():
        # Launches llama-server if not running
```

### 4.2 Configuration
**File**: `app/main.py` (Settings class)

```python
class Settings:
    inference_service_url: str = "http://0.0.0.0:8010"
    content_pipeline_url: str = "http://content-pipeline:8001"
    llama_server_host: str = "127.0.0.1"
    llama_server_port: int = 8081
    llama_model_path: str = "/models/model.gguf"
    llama_context_size: int = 2048
    llama_max_tokens: int = 256
    llama_temperature: float = 0.4
    llama_top_p: float = 0.9
    llama_prompt_cache_size: int = 128
    stream_batch_chars: int = 120
    prompt_context_limit: int = 1800
```

### 4.3 Request Models

```python
class ChatRequest(BaseModel):
    question: str
    grade: int | None = None
    subject: str | None = None
    chapter: str | None = None
    topic: str | None = None
    language: str | None = None
    limit: int = Field(default=5, ge=1, le=20)
    stream: bool = False
    max_tokens: int | None = None
    temperature: float | None = None
    top_p: float | None = None

class TutorRequest(ChatRequest):
    hint_style: str = Field(default="guided")

class InferenceResponse(BaseModel):
    answer: str
    model: str
    context: list[ContextResult] = Field(default_factory=list)
```

### 4.4 Prompt Cache
```python
class PromptCache:
    def __init__(max_size: int):
        self._store: OrderedDict[str, str] = OrderedDict()
    
    def get(key: str) -> str | None:
        # LRU cache lookup
    
    def set(key: str, value: str):
        # LRU cache store
```

---

## 5. QDRANT VECTOR STORE INTEGRATION

**Location**: `/home/akash/Desktop/PIHUB/backend/shared/vector_store.py`

### 5.1 Core Functions

```python
def make_qdrant_client(url: str) -> QdrantClient:
    return QdrantClient(url=url)

def ensure_collection(client: QdrantClient, collection_name: str, 
                      vector_size: int) -> None:
    # Creates collection if not exists
    # Uses COSINE distance metric
    # Vector size: typically 384 (from embedding model)

def upsert_chunks(client: QdrantClient, collection_name: str,
                  embeddings: list[list[float]], texts: list[str],
                  metadatas: list[dict]) -> list[str]:
    # Inserts/updates chunks as Qdrant points
    # Returns: list of point IDs
    
    # Payload structure:
    # {
    #   "text": str,
    #   "grade": int,
    #   "subject": str,
    #   "chapter": str,
    #   "section": str,
    #   "topic": str,
    #   "chunk_type": str,
    #   "language": str,
    #   "difficulty": str,
    #   "keywords": [str],
    #   ...
    # }

def build_filter(metadata: dict = None) -> qmodels.Filter | None:
    # Builds Qdrant filter from metadata
    # All conditions are AND'ed
    # Skips None values
```

### 5.2 Qdrant Configuration

**Collection Name**: `educational_chunks` (from settings)  
**Vector Size**: 384 (from SimpleEmbeddingModel)  
**Distance Metric**: COSINE  
**URL**: `http://qdrant:6333` (via docker-compose)

### 5.3 Data Flow

```
Content Pipeline
  ↓
  Chunk
  ↓
  Embed (SimpleEmbeddingModel)
  ↓
  upsert_chunks()
  ↓
Qdrant Collection (educational_chunks)
  ↓
  Retrieval (search with filters + reranking)
  ↓
  EducationalRetrievalEngine (hybrid ranking)
  ↓
  Pack Service (aggregate into packs)
```

---

## 6. SHARED LIBRARIES

**Location**: `/home/akash/Desktop/PIHUB/backend/shared`

### 6.1 Schemas (`schemas.py`)

#### Request Models
- `SearchRequest` - Query + limit + optional metadata filter
- `ChapterRequest` - Chapter search request
- `SubjectRequest` - Subject search request
- `TextbookIngestRequest` - Ingest request with metadata
- `DirectoryIngestRequest` - Batch directory ingest
- `DebugRetrievalRequest` - Debug retrieval with tracing

#### Response Models
- `SearchResponse` - List of chunk results
- `IngestResponse` - File ingestion result
- `HealthResponse` - Service health status

#### Data Models
```python
class Metadata(BaseModel):
    grade: int | None = None
    subject: str | None = None
    chapter: str | None = None
    topic: str | None = None
    language: str | None = None

class ChunkResult(BaseModel):
    id: str
    score: float | None = None
    text: str
    metadata: dict[str, Any]

class EducationalResource(BaseModel):
    resource_type: "experiment|simulation|animation|diagram|..."
    topic: str
    grade_range: list[int] = []
    offline_supported: bool = True
    interactive: bool = False
    url: str | None = None
    metadata: dict[str, Any] = {}
```

---

### 6.2 Pack Schemas (`pack_schemas.py`)

#### PackChunk
```python
class PackChunk(BaseModel):
    chunk_id: str
    text: str
    embedding: List[float]
    metadata: Dict[str, Any]
    score: float = 0.0
```

#### PackMetadata
```python
class PackMetadata(BaseModel):
    pack_id: str              # e.g., "class7_science"
    version: str = "1.0"
    grade: Optional[int]
    subject: Optional[str]
    language: Optional[str]
    created_at: datetime
    chunk_count: int
    media_count: int
    compressed_size_mb: float
    uncompressed_size_mb: float
    compression_ratio: float
```

#### PackManifest
```python
class PackManifest(BaseModel):
    metadata: PackMetadata
    chunks: List[PackChunk]
    media_files: Dict[str, str]
    checksum: Optional[str]  # SHA256
    archive_path: Optional[str]
```

#### Pack Generation Request/Response
```python
class PackGenerationRequest(BaseModel):
    pack_type: str  # "class", "chapter", "language"
    grade: Optional[int]
    subject: Optional[str]
    chapter: Optional[str]
    language: Optional[str]
    include_media: bool = False
    compression: str = "gzip"
    quantize_embeddings: bool = False

class PackGenerationResponse(BaseModel):
    pack_id: str
    version: str
    status: str  # "pending", "processing", "completed", "failed"
    chunk_count: int
    media_count: int
    estimated_size_mb: float
    manifest_url: Optional[str]
    download_url: Optional[str]
    created_at: datetime
```

---

### 6.3 Configuration (`config.py`)

```python
class Settings:
    # Service URLs
    qdrant_url = "http://qdrant:6333"
    qdrant_collection = "educational_chunks"
    
    # Storage paths
    upload_dir = "/shared/uploads"
    work_dir = "/shared/work"
    content_dir = "/shared/content"
    curriculum_graph_path = "/shared/work/curriculum_graph.json"
    curriculum_relation_graph_path = "/shared/work/curriculum_relation_graph.json"
    pack_storage_path = "/shared/packs"
    
    # Features
    enable_auto_ingestion = False
    enable_semantic_educational_chunking = True
    enable_curriculum_graph_engine = True
    enable_educational_retrieval_engine = True
    
    # Curriculum
    textbooks_root = "/home/akash/Desktop/PIHUB/TEXTBOOKS"
    curriculum_build_dir = "/shared/curriculum"
    max_concurrent_compilation_tasks = 2
```

---

### 6.4 Curriculum Graph (`curriculum_graph.py`)

```python
@dataclass
class Concept:
    name: str
    description: str
    level: int = 1           # Complexity 1-10
    prerequisites: list[str]
    related_topics: list[str]

@dataclass
class Topic:
    name: str
    description: str
    concepts: list[Concept]
    duration_minutes: int = 30
    learning_objectives: list[str]

@dataclass
class Chapter:
    name: str
    number: int
    description: str
    topics: list[Topic]
    learning_outcomes: list[str]

@dataclass
class Subject:
    name: str
    description: str
    chapters: list[Chapter]
    total_hours: float = 0.0

@dataclass
class Grade:
    number: int
    subjects: list[Subject]
```

#### Key Methods
```python
def infer_topics_for_query(query: str) -> list[str]:
    # Returns potential topics for query string
    
def infer_subject_for_query(query: str) -> str | None:
    # Returns likely subject
    
def infer_concepts_for_text(text: str, limit: int = 4) -> list[str]:
    # Returns concepts mentioned in text
```

---

## 7. EMBEDDING MODEL

**Class**: `SimpleEmbeddingModel` (in `content-pipeline/app/main.py`)

```python
class SimpleEmbeddingModel:
    def __init__(dimension: int = 384):
        self.dimension = 384
    
    def encode(texts: list[str] | str, 
               normalize_embeddings: bool = True) -> list[list[float]]:
        # Hash-based embeddings
        # Not production-grade, but deterministic
```

### Embedding Algorithm
1. Tokenize text (alphanumeric tokens only)
2. For each token, hash using Blake2b (8-byte digest)
3. Convert hash to index within dimension space
4. Accumulate counts in vector
5. L2 normalize if requested

**Note**: This is a placeholder implementation. Production should use:
- `BAAI/bge-small-en-v1.5` (384-dim)
- `sentence-transformers` library
- Or OpenAI embeddings API

---

## 8. RETRIEVAL PIPELINE

### Complete Flow

```
1. USER QUERY
   ↓
2. Content Pipeline receives SearchRequest
   - query: str
   - limit: int
   - metadata: Optional[Metadata]
   ↓
3. CURRICULUM INFERENCE
   - Infer subject from query
   - Infer topics from query
   - Get prerequisite topics
   - Get related topics
   ↓
4. QDRANT SEARCH
   - Encode query to embedding (SimpleEmbeddingModel)
   - Build metadata filter (grade, subject, chapter, language)
   - Search Qdrant with filter
   - Returns top K raw hits (score + payload)
   ↓
5. HYBRID RERANKING (EducationalRetrievalEngine)
   For each hit:
   - Calculate semantic score (vector similarity)
   - Calculate lexical score (token overlap)
   - Calculate chunk_type_score (query-type matching)
   - Calculate topic score (exact/prereq/related)
   - Calculate subject_match
   - Calculate chapter_match
   - Calculate educational_score (weighted combination)
   - final_score = 0.45*semantic + 0.25*lexical + 0.30*educational
   ↓
6. RANKING & FILTERING
   - Sort by final_score descending
   - Drop results with final_score < 0.25
   - Truncate to limit
   ↓
7. RESPONSE
   - Return ranked chunks with debug info
```

### Configuration Parameters
- Semantic weight: 0.45
- Lexical weight: 0.25
- Educational weight: 0.30
- Topic weight: 0.40 (of educational)
- Chapter weight: 0.20 (of educational)
- Subject weight: 0.15 (of educational)
- Chunk type weight: 0.25 (of educational)
- Min score threshold: 0.25

---

## 9. VALIDATION SYSTEMS

### 9.1 Pack Validation Layers

```
PackValidator
├── ManifestValidator
│   └── Checks: pack_id, version, required fields
├── RetrievalValidator
│   └── Checks: index integrity, chunk references
├── GlossaryValidator
│   └── Checks: term uniqueness, definition format
├── QuizValidator
│   └── Checks: question/answer pairs, options
└── EducationalQualityValidator
    ├── Completeness check (all artifacts present)
    └── Score validation (0.0-1.0 ranges)
```

### 9.2 Validation Output

```python
class PackValidationResult(BaseModel):
    valid: bool
    errors: list[str]
    warnings: list[str]
```

---

## 10. INTEGRATION POINTS

### Service Dependencies

```
┌─────────────────────────────────────────────────────────┐
│                    Client/Frontend                       │
└────────────┬─────────────────────────┬──────────────────┘
             │                         │
             ▼                         ▼
    ┌─────────────────┐        ┌───────────────────┐
    │  Content        │        │   Pack            │
    │  Pipeline       │        │   Service         │
    │  (8001)         │        │   (8030)          │
    └────┬─────┬──────┘        └────┬──────┬───────┘
         │     │                    │      │
         │     └────────┬───────────┘      │
         │              │                   │
         ▼              ▼                   ▼
    ┌─────────────────────────────────────────────┐
    │   Qdrant Vector Store (6333)                │
    │   Collection: educational_chunks           │
    │   - Chunks with embeddings & metadata      │
    │   - Supports semantic search               │
    │   - Metadata filtering                     │
    └─────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────┐
    │   Inference Service (8010)                  │
    │   - Llama text generation                   │
    │   - Summaries, quizzes, explanations        │
    │   - Optional for content generation         │
    └─────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────┐
    │   Shared Storage (/shared)                  │
    │   - /uploads: User uploads                  │
    │   - /work: Processing workspace             │
    │   - /content: Ingested content              │
    │   - /packs: Generated packs                 │
    │   - /curriculum: Curriculum graphs          │
    └─────────────────────────────────────────────┘
```

---

## 11. KEY DATA STRUCTURES

### Chunk (Core Unit)
```python
{
    "text": str,              # Content
    "metadata": {
        "grade": int,
        "subject": str,
        "chapter": str,
        "section": str,
        "topic": str,
        "chunk_type": str,    # definition, formula, example, etc.
        "language": str,
        "difficulty": str,
        "keywords": [str],
        "topics": [str],
        "concepts": [str],
        "source": str
    }
}
```

### Pack (Compilation)
```python
{
    "pack_id": str,
    "metadata": {
        "grade": int,
        "subject": str,
        "chapter": str,
        "language": str,
        "version": str
    },
    "artifacts": {
        "content": [chunks],
        "glossary": [terms],
        "quizzes": [questions],
        "flashcards": [cards],
        "summaries": [summaries],
        "enrichment": {resources},
        "retrieval_index": {index}
    }
}
```

---

## 12. TYPICAL WORKFLOWS

### Workflow 1: Ingest Textbook → Generate Pack

```
1. POST /ingest/textbook
   - Upload textbook file
   - Set grade, subject, chapter, language
   
2. Pipeline processes:
   - Extract text from PDF
   - Merge paragraphs
   - Classify chunk types
   - Build metadata
   - Generate embeddings
   - Upsert to Qdrant
   
3. Response: chunks_created count

4. POST /packs/generate (via pack-service)
   - Specify grade, subject
   - PackGenerator queries Qdrant
   - Compiles all chunks
   - Generates summaries, glossary, quizzes
   - Creates archive
   - Stores manifest
   
5. Response: pack_id, download URL
```

### Workflow 2: Search → Retrieve → Rank

```
1. POST /rag/search
   - query: "What is photosynthesis?"
   - limit: 5
   
2. Content Pipeline:
   - Infer subject: "Biology"
   - Infer topics: ["photosynthesis", "chlorophyll"]
   - Get prerequisites: ["cell structure"]
   - Get related: ["respiration"]
   
3. Qdrant Search:
   - Encode query
   - Search with filter
   - Get top 20 candidates
   
4. EducationalRetrievalEngine:
   - Hybrid ranking (semantic + lexical + educational)
   - Filter by score threshold
   - Return top 5
   
5. Response: ranked chunks with debug info
```

### Workflow 3: Preview Pack

```
1. GET /packs/class7_science/preview
   
2. Pack Service:
   - Load manifest
   - Load all artifacts
   - Calculate quality scores
   - Build preview response
   
3. Response: 
   - Manifest with metadata
   - Sample summaries, glossary, quizzes
   - Quality metrics
   - File sizes
```

---

## 13. PERFORMANCE CONSIDERATIONS

### Caching
- **Prompt Cache**: 128 entries in inference service
- **Curriculum Graph**: Loaded at startup
- **Embedding Model**: Reused instance

### Compression
- **Pack Storage**: gzip (default), zstd, xz options
- **Embedding Quantization**: Optional (reduces pack size)

### Scalability
- **Concurrent Tasks**: Limited to 2 (configurable)
- **Qdrant Limit**: 10,000 chunks per query
- **Batch Ingestion**: Directory-based bulk processing

### Limits
- **Search Limit**: 1-50 chunks (default 5)
- **Question Limit**: 1-20 (default 5)
- **Context Window**: 1800 chars (prompt_context_limit)

---

## 14. ERROR HANDLING & VALIDATION

### Pipeline Validations
1. **Path validation**: Prevents directory traversal
2. **Metadata validation**: Required fields enforced
3. **Embedding dimension**: Verified against Qdrant collection
4. **Pack integrity**: SHA256 checksums

### API Error Codes
- `400` - Invalid request (bad metadata, path traversal)
- `404` - Pack/resource not found
- `409` - Pack already exists
- `500` - Server error (Qdrant, file system)

---

## 15. MONITORING & DEBUGGING

### Health Endpoints
- `GET /health` (all services)
- Returns service status, dependency checks
- Detailed error messages

### Debug Endpoints
- `GET /debug/curriculum` - Curriculum graph structure
- `GET /debug/curriculum-relations` - Relation graph
- `GET /debug/metadata` - Metadata structure
- `POST /rag/search` with `include_debug=true` - Ranking details

### Logging
- Service logs to `LOG_LEVEL` (default INFO)
- All major operations logged with durations
- Pack generation progress tracked

---

## Summary Architecture Table

| Component | Port | Purpose | Key Input | Key Output |
|-----------|------|---------|-----------|------------|
| content-pipeline | 8001 | Ingest, chunk, retrieve | Files, queries | Chunks in Qdrant |
| pack-service | 8030 | Compile packs | Grade/subject/chapter | .tar.gz archives |
| inference-service | 8010 | LLM generation | Text + prompt | Generated text |
| qdrant | 6333 | Vector search | Embeddings | Ranked results |

---

## File Reference Index

| Function | File |
|----------|------|
| Chunking | `content-pipeline/app/content_pipeline/educational_chunker.py` |
| Retrieval | `content-pipeline/app/retrieval_engine/educational_retrieval_engine.py` |
| Quizzes | `content-pipeline/app/educational_intelligence/quiz_generator.py` |
| Summaries | `content-pipeline/app/educational_intelligence/summary_generator.py` |
| Pack Gen | `pack-service/app/pack_generator.py` |
| Validation | `pack-service/app/validation/pack_validator.py` |
| Storage | `pack-service/app/pack_storage/pack_repository.py` |
| Schemas | `shared/schemas.py`, `shared/pack_schemas.py` |
| Vector Store | `shared/vector_store.py` |
| Config | `shared/config.py` |
| Curriculum | `shared/curriculum_graph.py` |

---

**Last Updated**: May 18, 2026
