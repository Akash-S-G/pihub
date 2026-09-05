# PIHUB — Full System Audit & Architecture Reference

Date: July 2026 · Branch: `dev` · Scope: whole system — architecture, services,
endpoints, data locations, access, inter-service communication, and improvement
suggestions with modern open-source tooling.

---

## 1. System overview

PIHUB is an **offline-first educational content appliance**: textbook PDFs go in on a
build host, enriched learning packs come out, and a Raspberry-Pi-class node serves
students in a classroom LAN with zero internet. Nine containers, one nginx front door.

```
                                 ┌──────────────────────────────────────────┐
 Internet (build time only)      │              docker network              │
   │  web search / cobalt        │                                          │
   ▼                             │  ┌─────────┐   ┌──────────────────────┐  │
 ┌───────────┐   :80             │  │  nginx  │──▶│   gateway :8000      │  │
 │  clients  │────────────────────▶ │ (:80)   │   │  (fan-out router)    │  │
 └───────────┘                   │  └─────────┘   └──────────┬───────────┘  │
                                 │        ┌──────────┬───────┼──────┬────────────┐
                                 │        ▼          ▼       ▼      ▼            ▼
                                 │  content-     inference  pihub  pack-   experiment-
                                 │  pipeline      :8010     :8020  service  service
                                 │   :8001          │              :8030    :8040
                                 │     │            │                │   voice-service
                                 │     ▼            ▼                │       :8050
                                 │  qdrant:6333  llama.cpp/ollama    │
                                 │  mongo:27017  (in-container)      │
                                 │  cobalt:9000                      │
                                 └───────────────────────────────────┘
```

Two compose files:
- `backend/docker-compose.yml` — dev/build host (only nginx published: `:80`)
- `backend/docker-compose.server.yml` — server variant (⚠ publishes 6333/6334, 8001,
  8010, 8050 directly — see audit §6)

---

## 2. Services, one by one

### 2.1 nginx (`pihub-nginx`, port 80 → host)
- Image `nginx:1.27-alpine`; config `backend/nginx/nginx.conf`
- Routes: `location /` → gateway; `~ ^/api/(v1/)?voice/` → gateway (larger body/timeouts)
- **Access:** `http://<host>/` — the only intended public entry.

### 2.2 gateway (`pihub-gateway`, :8000)
FastAPI fan-out router — ~110 endpoints, proxies to every backend service.
Key groups (all reachable via nginx):
| Group | Examples | Proxies to |
|---|---|---|
| Ingest | `POST /upload`, `/ingest/pdf`, `/ingest/textbook`, `/ingest/generated-pack`, `/ingest/directory` | content-pipeline |
| RAG | `POST /rag/search`, `/rag/curriculum_search`, `GET /rag/chapter`, `/rag/subject` | content-pipeline |
| AI | `POST /ai/chat`, `/ai/tutor`, `/ai/tutor/evaluate`, `GET /ai/health` | inference-service |
| Voice | `POST /voice/query|tts|stt`, `GET /voice/audio/{id}`, `/voice/metrics` | voice-service |
| Packs | `GET /packs`, `/packs/catalog`, `/packs/coverage`, `/packs/recommended`, `POST /packs/generate`, `GET /packs/{id}/manifest|download` | pack-service / pihub |
| PDF library | `GET /api/v1/pdf/catalog|resolve|book/...|chapter/...|file/{book_id}` | pack-service |
| Experiments | `GET /experiments`, `/experiments/catalog`, `/simulations/{path}`, `/experiment-templates`, `POST /experiment-runs`, run events/complete | experiment-service |
| Classroom | `POST/GET /classroom/sessions`, assignments, submissions, `/classroom/analytics` | experiment-service |
| Learning | `GET /flashcards`, `/quizzes`, `/glossary`, `/summaries`, `POST /planner/lesson` | pack/content |
| Progress | `POST /progress`, `/quiz-sessions`… | pihub node |
| Sync/devices | `GET/POST /sync`, `/devices`, `/discovery`, `/discovery/beacon` | pihub node |
| Analytics | `/analytics/student|experiment|system|top-experiments`, `/metrics/tutor|retrieval` | experiment/inference |
| Debug | `/debug/curriculum|metadata|chunks|retrieval|similarity|pack-preview` | content-pipeline |

### 2.3 content-pipeline (`:8001`) — the build brain
Endpoints: `/health`, `POST /ingest/pdf|textbook|generated-pack|directory`,
`POST /admin/reset-rag`, `POST /rag/search|curriculum_search`, `GET /rag/chapter|subject`,
8× `/debug/*`, `POST /build/artifacts`, `POST /build/pack`, `GET /build/quality/{path}`,
`POST /build/agentic-artifacts`, **`POST /build/enriched-artifacts` (new)**,
`GET /build/report/{job_id}`, `GET /reports`.

Internals: PDF → docling/pymupdf extraction → educational chunker (sentence-aware) →
BGE-small embeddings → Qdrant. `ArtifactAgent` (analyze→plan→generate→critique→refine)
produces summaries/quiz/flashcards/glossary. **`EnrichedContentAgent`** adds per-topic
web videos/articles/sims (kn+en), Cobalt downloads + ffmpeg compression, Mongo metadata,
Qdrant `enrichment_resources`.

### 2.4 inference-service (`:8010`)
`POST /ai/chat`, `/ai/tutor(+debug/evaluate)`, 8× `POST /ai/content/*` generators
(summary, chapter-notes, flashcards, quiz, glossary, learning-objectives,
misconceptions, applications), `GET /ai/health`, `/metrics/tutor|retrieval`.
Backends: llama.cpp server (`/models/model.gguf`, ctx 2048) or Ollama
(`CONTENT_GENERATION_BACKEND=ollama`, model `gemma4`). RAG context via content-pipeline.

### 2.5 pihub node (`:8020`) — classroom runtime
Device registry (register/heartbeat/trust/reconnect), pack catalog + download,
sync engine (`POST /sync`, `/sync/process`, retry), student progress + quiz sessions,
hotspot deployment endpoints (`/deployment/hotspot/*`, `/deployment/startup/*`),
broadcast (`POST /broadcast/pack/{id}`), cache stats. Auth: `PIHUB_ADMIN_TOKEN`,
`PIHUB_DEVICE_TOKEN_SECRET` (⚠ defaults `change-me` in compose).

### 2.6 pack-service (`:8030`)
`POST /packs/generate`, `/packs/import/generated`, `/packs/import/phet`, `/health`.
Compiles chunks + artifacts + PDFs + PhET sims into `.otpack` bundles + manifests.

### 2.7 experiment-service (`:8040`)
Largest API surface: manifest validate/migrate/resolve/compatibility, builder CRUD +
publish/archive, sharing sign/verify/trust/import/export + analytics, classroom
sessions/assignments/submissions, experiment runs + events + completion,
`POST /ai/generate-experiment|refine-experiment|explain-experiment`.

### 2.8 voice-service (`:8050`)
`POST /voice/stt` (faster-whisper small int8, or Gemma-4 audio fallback),
`POST /voice/tts` (Svara TTS GGUF + SNAC ONNX decoder, 24 kHz),
`POST /voice/query` (STT → tutor → TTS roundtrip), `GET /voice/audio/{asset_id}`,
`/voice/metrics`, `/health`. Only service with a compose healthcheck.

### 2.9 Infrastructure containers
- **qdrant** `v1.13.4` (:6333 HTTP/:6334 gRPC) — vector DB
- **mongo** `7.0` (:27017) — enrichment media metadata (new)
- **cobalt** `latest` (:9000) — media downloader API (new; build-time only)

---

## 3. Data storage map (exact locations)

| Data | Store | Exact location | Access |
|---|---|---|---|
| Text chunks + embeddings | Qdrant `educational_chunks` | docker volume `qdrant_data` → `/qdrant/storage` (host: `/var/lib/docker/volumes/backend_qdrant_data/_data`) | `GET http://qdrant:6333/collections/educational_chunks` (inside network) |
| Enrichment records (new) | Qdrant `enrichment_resources` | same volume | same, collection name differs |
| Media metadata (new) | MongoDB `pihub.media` | volume `mongo_data` → `/data/db` | `mongosh mongodb://mongo:27017/pihub` → `db.media.find()` |
| Downloaded videos (new) | filesystem | volume `shared_storage` → `/shared/media/videos/<blake2b12>.mp4` | any container mounting `/shared` |
| Downloaded images (new) | filesystem | `/shared/media/images/<hash>.<ext>` | same |
| Uploaded PDFs | filesystem | `/shared/uploads` (`UPLOAD_DIR`) | content-pipeline |
| Build workdir + curriculum graph | filesystem | `/shared/work`, `/shared/work/curriculum_graph.json` | content-pipeline, pack-service |
| Compiled packs | filesystem | `/shared/packs` (`PACK_STORAGE_PATH`), PDF manifests at `/shared/packs/pdf_manifests/pdf_manifest.json` | pack-service; served via gateway `/packs/{id}/download` |
| Textbook PDF library | host bind (ro) | `../TEXTBOOKS` → `/shared/textbooks` | pack-service PDF endpoints |
| PhET simulations | host bind (ro) | `../phet_downloads` → `/shared/phet_downloads` (pack-service) and `/shared/simulations` (experiment-service) | gateway `/simulations/{path}` |
| Generated pack input | host bind (ro) | `../generated_pack` → `/shared/generated_pack` | ingest endpoints |
| Classroom node DB | SQLite | host `backend/pihub/storage/pihub.sqlite3` (`PIHUB_DB_PATH=/storage/pihub.sqlite3`) | pihub node only; file readable on host |
| Node packs/cache/logs | host bind | `backend/pihub/{packs,storage,cache,logs}` | host filesystem |
| LLM GGUF models | host bind | `backend/inference-service/models/` → `/models` (gitignored) | inference-service |
| Voice models (Svara GGUF, SNAC ONNX, gemma4 cache) | host bind | `backend/voice-service/models/` (3.9 GB, now gitignored + purged from history) | voice-service |
| Embedding model cache | filesystem | `/shared/models/sentence-transformers/{embedding,retrieval}` | content-pipeline |
| Voice audio assets | filesystem | `/shared/voice/audio` + `/shared/voice/audio_manifest.json` | voice-service; served via `/voice/audio/{id}` |
| All service logs | volume `backend_logs` | `/logs` in each container, `/var/log/{nginx,qdrant,mongo}` | `docker logs <name>` or volume |

**Quick access cheatsheet (from host):**
```bash
curl http://localhost/health                          # gateway via nginx
docker exec -it pihub-qdrant sh                       # or curl inside network:
docker run --rm --network backend_default curlimages/curl -s http://qdrant:6333/collections
docker exec -it pihub-mongo mongosh pihub --eval 'db.media.countDocuments()'
sqlite3 backend/pihub/storage/pihub.sqlite3 '.tables'
docker volume inspect backend_shared_storage          # find _data path, browse media/packs
```

---

## 4. How services communicate

- **Protocol:** plain HTTP/JSON over the compose bridge network; DNS by service name
  (`http://content-pipeline:8001`, `http://qdrant:6333`, `http://mongo:27017`,
  `http://cobalt:9000`). No message queue, no gRPC (Qdrant gRPC port exposed but unused).
- **Topology:** hub-and-spoke. Gateway holds URLs of all 7 services via env and fans out.
  Direct service-to-service calls that bypass the gateway:
  - inference-service → content-pipeline (`CONTENT_PIPELINE_URL`) for RAG context
  - voice-service → inference-service (`VOICE_TUTOR_URL=/ai/tutor`) for voice tutoring
  - pack-service → inference-service (Gemma content generation during pack builds)
  - content-pipeline → qdrant, mongo, cobalt, + outbound web (enrichment, build-time)
- **Startup order:** `depends_on` (no health conditions, except voice healthcheck) —
  services race; clients retry/degrade.
- **Auth between services: none** (trusted network assumption). Client-facing auth only
  on pihub node (admin/device tokens).

---

## 5. Git history purge — DONE ✅

- Backup bundle created first: `/tmp/pihub-backup-*.bundle` (37 MB, all refs)
- Investigation showed the 3.9 GB gemma4 blobs were **never in reachable history** —
  only tiny cache/config files (~17 KB max) were committed; the 3 GB of packfiles were
  unreachable objects + reflog leftovers from local experiments
- Fix: `git reflog expire --expire=now --all` + `git gc --prune=now --aggressive`
- **`.git`: 3.1 GB → 34 MB** (size-pack 32.9 MiB); largest reachable blob 7.7 MB
  (phet index.html — kept intentionally, PhET sims are product content)
- ✅ **No SHAs were rewritten** — remote `dev` tip `d903d4c` is an ancestor of local
  `dev`; a plain `git push pihub dev` fast-forwards. No force-push, no re-clones needed.

---

## 6. Suggestions — new features & modern open-source upgrades

### Retrieval quality
1. **Hybrid search (BM25 + dense) with Qdrant** — Qdrant ≥1.10 supports sparse vectors
  natively (`bm42`/`splade`). NCERT text has exact-term questions ("What is rancidity?")
  where BM25 beats cosine. One extra named vector per point; biggest single retrieval win.
2. **Reranker on top-k** — `BAAI/bge-reranker-v2-m3` (multilingual, runs CPU int8 via
  ONNX) rescoring top-20 → top-5 dramatically improves tutor context. ~80 ms on Pi 5.
3. **Multilingual embeddings** — current `bge-small-en-v1.5` is English-only; Kannada
  chunks embed poorly. Switch to `BAAI/bge-m3` (or `intfloat/multilingual-e5-small`
  for Pi budget) so kn/en share one vector space → cross-lingual retrieval
  (ask in Kannada, retrieve English chunk, answer in Kannada).

### Inference
4. **Structured output via llama.cpp GBNF / Ollama JSON schema** — quiz/flashcard
  generators can enforce JSON grammar at decode time; eliminates parse-retry loops
  (currently `CONTENT_GENERATION_RETRIES=3`).
5. **Qwen3-4B-Instruct or Gemma-4-E4B as content model** — both outperform older 4B-class
  models on multilingual (incl. Indic) generation; GGUF Q4_K_M fits Pi-5 8 GB.
6. **Speculative decoding on llama.cpp** (draft model) — build-host generation 1.5–2×
  faster; zero quality change.

### Voice
7. **Replace faster-whisper small with `AI4Bharat/IndicConformer` or Whisper-large-v3-turbo
  int8** for Kannada STT accuracy (turbo is 8× faster than large-v3, similar WER).
8. **Piper TTS** as lightweight fallback voice — 20 MB models, real-time on Pi Zero-class
  hardware; keep Svara as premium voice.

### Enrichment pipeline (the new agent)
9. **SearxNG container** as the search backend instead of scraping DuckDuckGo HTML —
  self-hosted metasearch with a stable JSON API, fits the appliance philosophy, removes
  the most fragile dependency. Drop-in at `_duckduckgo_search`.
10. **Wikimedia Commons + NASA/Wellcome open media APIs** for topic images —
  properly licensed, keyless, high quality; better than scraped thumbnails.
11. **Bhashini / IndicTrans2** (AI4Bharat, open) — machine-translate English enrichment
  descriptions to Kannada at build time so every resource card is bilingual even when
  the web has no Kannada source.

### Platform
12. **Compose profiles** — `profiles: ["build"]` on cobalt (+mongo if snapshotted):
  Pi runtime = 6 containers instead of 9.
13. **Healthchecks + `service_healthy` depends_on** everywhere (only voice has one).
14. **Uptime-Kuma** (single container, ~50 MB) as the classroom "is everything up"
  dashboard for teachers — zero config against existing `/health` endpoints.
15. **SQLite → Litestream** replication of `pihub.sqlite3` to `/shared` — crash-safe
  student progress with zero infra.
16. **Caddy instead of nginx** (optional) — automatic internal TLS with one-line config;
  or keep nginx and add mkcert certs for LAN HTTPS.
17. **API auth at the gateway** — one FastAPI dependency checking a static bearer from
  `.env` closes the biggest security gap (unauthenticated internal APIs, esp. in
  `docker-compose.server.yml` which publishes 6333/8001/8010/8050 to the host).
18. **Observability on the cheap** — enable uvicorn access logs to `/logs` + a tiny
  `GET /metrics` (prometheus_client) per service; scrape ad-hoc, no Prometheus server
  needed on the Pi.

### Priority order (my pick)
| Rank | Item | Why first |
|---|---|---|
| 1 | #3 multilingual embeddings | Kannada retrieval is silently broken today |
| 2 | #17 gateway auth + stop publishing internal ports | biggest security hole |
| 3 | #1 hybrid search | largest quality win per effort |
| 4 | #9 SearxNG | de-risks the new enrichment agent |
| 5 | #12/#13 profiles + healthchecks | Pi footprint + reliability |
| 6 | #2 reranker | tutor answer quality |
| 7 | #11 IndicTrans2 | true bilingual enrichment cards |
