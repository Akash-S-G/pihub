# Distributed Educational AI Ecosystem Backend

This folder contains the Week 1 and Week 2 backend stack:

- FastAPI gateway
- Content pipeline service
- Qdrant vector database
- Nginx reverse proxy
- Docker Compose orchestration

## Quick Start

```bash
cd backend
cp .env.example .env
docker compose up --build
```

## Week 3 and Week 4 Services

The compose stack now includes:

- `inference-service` for educational AI generation
- `pihub` for classroom sync and caching

The inference service expects a GGUF model mounted at `backend/inference-service/models/model.gguf`.
Without that file, `/ai/health` reports a degraded state and generation endpoints return a clear `503`.

## Common Commands

```bash
docker compose up --build qdrant content-pipeline inference-service pihub gateway nginx
```

```bash
docker compose logs -f inference-service
docker compose logs -f pihub
```

## Services

- Gateway: proxied through Nginx on `http://localhost`
- Content pipeline: internal service at `http://content-pipeline:8001`
- Qdrant: internal service at `http://qdrant:6333`
- Inference service: internal service at `http://inference-service:8010`
- PiHub: internal service at `http://pihub:8020`

## Health Checks

- `GET /health`
- `GET /rag/search`
- `GET /rag/chapter`
- `GET /rag/subject`
- `POST /content/upload`
- `POST /upload`

## Example Request

```bash
curl -X POST http://localhost/content/upload \
  -F "file=@sample.pdf" \
  -F "grade=5" \
  -F "subject=Science" \
  -F "chapter=Plants" \
  -F "topic=Photosynthesis" \
  -F "language=English"
```

```bash
curl -X POST http://localhost/rag/search \
  -H "Content-Type: application/json" \
  -d '{"query":"How do plants make food?","limit":5}'
```

```bash
curl -X POST http://localhost/ai/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"Explain photosynthesis for grade 5","grade":5,"subject":"Science","chapter":"Plants","language":"English"}'
```

```bash
curl -X POST http://localhost/devices \
  -H "Content-Type: application/json" \
  -d '{"device_name":"Class tablet 1","role":"student","classroom":"Classroom A"}'
```

```bash
curl -X POST http://localhost/sync \
  -H "Content-Type: application/json" \
  -d '{"action":"start","device_id":"demo-device","resource_type":"pack","resource_id":"science-pack-01","total_bytes":2048}'
```

## Testing Notes

1. Verify the compose topology with `docker compose config`.
2. Check `GET /health` on the gateway and confirm it reports content, Qdrant, inference, and PiHub status.
3. Mount a GGUF model into `backend/inference-service/models/model.gguf` before testing `/ai/chat` and `/ai/tutor`.
4. Register a device with `POST /devices`, then call `POST /devices/{device_id}/heartbeat` using the returned token in `X-Device-Token`.
5. Use `POST /sync` with `action=start` to create resumable classroom transfer sessions.
