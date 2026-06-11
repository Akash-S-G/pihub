# PIHUB Backend Architecture Upgrade Report

## Summary

This upgrade adds production-facing LAN hub endpoints at the gateway while preserving the existing tutor pipeline. The gateway remains the public API surface on port `8000` and proxies durable classroom state to `pihub`, pack metadata/assets to `pack-service`, RAG to `content-pipeline`, and tutoring to `inference-service`.

## New Endpoints

### Discovery

`GET /discovery`

Response:

```json
{
  "service": "PIHUB",
  "version": "1.0",
  "node_type": "hub",
  "api_port": 8000,
  "supports_rag": true,
  "supports_sync": true,
  "supports_assets": true
}
```

Diagnostics:

```text
[DISCOVERY] REQUEST_RECEIVED
[DISCOVERY] REQUEST_COMPLETED
```

### Tutor Capabilities

`GET /tutor/capabilities`

Response:

```json
{
  "streaming": true,
  "rag": true,
  "flashcards": true,
  "quizzes": true,
  "glossary": true,
  "summaries": true
}
```

### Pack Sync

`GET /packs/sync`

Response:

```json
{
  "server_version": "1.0",
  "packs": [
    {
      "pack_id": "string",
      "version": "string",
      "hash": "string",
      "updated_at": "string"
    }
  ]
}
```

### Pack Manifest

`GET /packs/{pack_id}/manifest`

Response:

```json
{
  "pack_id": "string",
  "version": "string",
  "metadata": {},
  "chunk_count": 0,
  "flashcard_count": 0,
  "quiz_count": 0,
  "glossary_count": 0,
  "summary_count": 0,
  "artifact_counts": {}
}
```

### Asset APIs

`GET /flashcards`

`GET /quizzes`

`GET /glossary`

`GET /summaries`

Supported query filters:

```text
grade
subject
chapter
topic
```

Response:

```json
{
  "items": [],
  "total": 0,
  "filters": {
    "grade": 6,
    "subject": "Mathematics",
    "chapter": "Fractions",
    "topic": "equivalent fractions"
  }
}
```

### Progress Sync

`POST /progress`

Request:

```json
{
  "student_id": "student-1",
  "grade": 6,
  "subject": "Mathematics",
  "chapter": "Fractions",
  "score": 80,
  "attempts": 3,
  "updated_at": "2026-06-06T10:00:00Z"
}
```

Response:

```json
{
  "status": "ok",
  "progress": {}
}
```

`GET /progress/{student_id}`

Response:

```json
{
  "student_id": "student-1",
  "progress": []
}
```

### Health Upgrade

`GET /health`

Response includes the legacy fields plus richer diagnostics:

```json
{
  "status": "healthy",
  "version": "1.0",
  "service": "gateway",
  "inference_service": true,
  "database": true,
  "pack_count": 0,
  "chunk_count": 0,
  "uptime_seconds": 0,
  "checks": {}
}
```

## Structured Logs

The gateway now emits structured start/end/error logs with category tags:

```text
[REQUEST]
[SYNC]
[PACK]
[RAG]
[TUTOR]
[DISCOVERY]
[PROGRESS]
```

The PiHub node also emits structured logs for local node APIs, including progress and sync endpoints.

## Docker Compatibility

No new Python packages or system packages are required. Changes are limited to application code and the existing SQLite database migration path in `PiHubStore._init_db()`.

The new `learning_progress` table is created automatically on PiHub startup.

## Backward Compatibility

Existing integrations are preserved:

- `POST /ai/tutor` behavior is unchanged.
- Existing `/packs`, `/sync`, `/devices`, `/classroom`, `/rag/*`, and debug endpoints remain available.
- `GET /health` still returns `status`, `service`, and `checks`, while adding richer top-level diagnostics.

## Example Curl Commands

```bash
curl http://localhost/discovery
curl http://localhost/tutor/capabilities
curl http://localhost/health
curl http://localhost/packs/sync
curl http://localhost/packs/PACK_ID/manifest
curl "http://localhost/flashcards?grade=6&subject=Mathematics"
curl "http://localhost/quizzes?grade=6&subject=Mathematics&chapter=Fractions"
curl "http://localhost/glossary?topic=photosynthesis"
curl "http://localhost/summaries?subject=Science"
curl -X POST http://localhost/progress \
  -H "Content-Type: application/json" \
  -d '{"student_id":"student-1","grade":6,"subject":"Mathematics","chapter":"Fractions","score":80,"attempts":3,"updated_at":"2026-06-06T10:00:00Z"}'
curl http://localhost/progress/student-1
```
