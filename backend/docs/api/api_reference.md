# PIHUB Backend API Reference

This document freezes the core backend API contracts for production integration.

---

## 1. Health APIs

### Get System Health
- **Endpoint:** `/health`
- **Method:** `GET`
- **Description:** Returns the aggregated health status of all backend services (Gateway, Content Pipeline, Inference, Pack Service, Qdrant).

**Response Schema:**
```json
{
  "status": "string",
  "service": "string",
  "checks": "object"
}
```
**Example Response:**
```json
{
  "status": "ok",
  "service": "gateway",
  "checks": {
    "gateway": "ok",
    "content_pipeline": {"status": "ok"},
    "qdrant": {"status_code": 200, "body": "qdrant"}
  }
}
```

---

## 2. Tutor APIs

### Ask AI Tutor
- **Endpoint:** `/ai/tutor`
- **Method:** `POST`
- **Description:** Submits a student question to the Concept Router and Local LLM. Returns an educational answer with the RAG context used.

**Request Schema:**
```json
{
  "question": "string (required)",
  "grade": "integer (optional)",
  "subject": "string (optional)",
  "chapter": "string (optional)",
  "topic": "string (optional)",
  "language": "string (optional)",
  "limit": "integer (optional, default: 5)",
  "stream": "boolean (optional, default: false)",
  "hint_style": "string (optional, default: 'guided')"
}
```
**Example Request:**
```json
{
  "question": "What is the surface area of a cylinder?",
  "grade": 10,
  "subject": "maths"
}
```

**Response Schema:**
```json
{
  "answer": "string",
  "model": "string",
  "context": [
    {
      "id": "string",
      "score": "float",
      "text": "string",
      "metadata": "object"
    }
  ]
}
```

---

## 3. Search APIs

### RAG Search
- **Endpoint:** `/rag/search`
- **Method:** `POST`
- **Description:** Performs semantic search across the educational curriculum chunks.

**Request Schema:**
```json
{
  "query": "string (required)",
  "limit": "integer (optional, default: 5)",
  "metadata": "object (optional filters)"
}
```
**Example Request:**
```json
{
  "query": "Arithmetic Progressions",
  "limit": 3,
  "metadata": {"subject": "maths"}
}
```

**Response Schema:**
```json
{
  "query": "string",
  "results": [
    {
      "id": "string",
      "score": "float",
      "text": "string",
      "metadata": "object"
    }
  ]
}
```

---

## 4. Pack APIs

### Generate Pack
- **Endpoint:** `/packs/generate` (Internal Pack Service)
- **Method:** `POST`
- **Description:** Compiles and compresses educational curriculum chunks, glossaries, quizzes, and embeddings into an offline-ready package.

**Request Schema:**
```json
{
  "pack_type": "string (class | chapter | language)",
  "grade": "integer (optional)",
  "subject": "string (optional)",
  "chapter": "string (optional)",
  "language": "string (optional, default: english)",
  "compression": "string (optional, default: gzip)"
}
```
**Example Request:**
```json
{
  "pack_type": "chapter",
  "grade": 5,
  "subject": "maths",
  "chapter": "animal jumps"
}
```

**Response Schema:**
```json
{
  "pack_id": "string",
  "version": "string",
  "status": "string",
  "chunk_count": "integer",
  "media_count": "integer",
  "estimated_size_mb": "float",
  "manifest_url": "string",
  "download_url": "string"
}
```

### List Packs
- **Endpoint:** `/packs`
- **Method:** `GET`
- **Description:** Returns the global registry of all generated packs.

**Response Schema:**
```json
{
  "packs": [
    {
      "pack_id": "string",
      "size_mb": "float",
      "status": "string",
      "download_url": "string",
      "manifest_url": "string"
    }
  ]
}
```

## Error Responses (Global)
All API endpoints will return standard HTTP error codes:
- `400 Bad Request` for invalid schemas or missing fields.
- `404 Not Found` for missing packs or chunks.
- `500 Internal Server Error` for upstream network issues or pipeline failures.
```json
{
  "detail": "Error message explanation"
}
```
