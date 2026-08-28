# Backend Improvement Ideas & Suggestions

Status: Draft / suggestions only — some items implemented (see notes).
Scope: Updating/refactoring existing code. No new features at MVP level.

> **DONE:** voice-service has been restored & gated behind `VOICE_SERVICE_ENABLED`
> (see §2). It is no longer in the default compose stack but can be re-enabled via the flag.

---

## 1. Teacher/Admin Resource-Input Interface (architecture)

### The logical framing
This is not an "either/or" with web scraping — the two solve different problems and should
coexist as **two ingestion sources** feeding one common pipeline.

| Approach | Best for | Precision |
|---|---|---|
| Web scraping | Bulk open resources (Wikipedia, PhET, Khan Academy), breadth | Low–medium |
| Teacher/admin UI | Syllabus, school textbooks, corrections, curated/domain files | High |

Pedagogical QA can't happen in a web scraper. Educational accuracy lives with the teacher, so
a protocol for them to inject curated/curated sources gives you a **source of truth** the scraper
cannot.

### Architecture direction (logical, not code)

```
            ┌──────────────────────────────────────────┐
            │        Content/ingestion store            │   ← source of truth
            │  (source + chapter + topic + tags + QA)   │
            └───────┬──────────────────────▲────────────┘
                    │  submit/curate        │ batch bulk
               manual│  (teacher/admin)     │ (scraper)
                    ▼                       │
            ┌──────────────────────────────────────────┐
            │             Ingest pipeline               │
            │   one entrypoint; provenance field        │
            │   ("scraped" | "teacher" | "admin")       │
            │   → chunk → embed → qdrant               │
            └──────────────────────────────────────────┘
```

### Key principle
Make the manual UI emit **the same ingest object the scraper emits**, tagged with a
`provenance` field and topic/chapter metadata. Then the existing
`content-pipeline` handles it without re-architecture — it becomes one more ingest path.

### Concrete gaps (logical)
1. Authenticated teacher/admin web UI (or gateway-proxied API endpoints).
2. Upload PDF/text + assign subject → chapter → topic.
3. Inject as "curated" source → existing ingest → qdrant.
4. Use for content too coarse/syllabus-specific to scrape.

---

## 2. Voice-service: restored & gated behind a flag (DONE)

Voice-service was removed from the active stack but is planned for reuse, so it has been
**restored from git and gated** behind a config flag rather than deleted. The full
implementation (gateway proxy/query/TTS/STT/metrics, WebSocket proxy, voice-service code)
is kept in the repo; when disabled it produces **no runtime noise or proxying attempts**.

### The gating knob
- `shared/config.py` — `voice_service_enabled` (alias `VOICE_SERVICE_ENABLED`), default `False`.
- When `False` (default), the gateway:
  - skips the `http://voice-service:8050/health` probe; `/health` reports `voice_service: {"healthy": true, "disabled": true}`
  - declares `voice`/`audio` capabilities as disabled
  - returns `HTTP 503 "Voice service disabled"` from `/voice/*`, `/api/voice/*`, and the `/voice/stream` WebSocket instead of proxying
- When `True`, all voice logic behaves as before. `voice_service_required` (default `False`) additionally marks the service as mandatory — the gateway reports `degraded` if its health probe fails.

### To re-enable
1. Set `VOICE_SERVICE_ENABLED=true` (and, if mandatory, `VOICE_SERVICE_REQUIRED=true`).
2. Add the `voice-service` container back to the compose stack (it is not part of the active
   stack; the service + Dockerfile are restored in the repo).

### Files involved
- `shared/config.py` — added `voice_service_enabled`
- `gateway/app/main.py` — gated route classification, retry logic, health probe, `/voice/*` routes, WebSocket proxy, and capability flags
- `nginx/nginx.conf` — no change needed; the `/api/(v1/)?voice/` location proxies to the gateway, which 503s cleanly when disabled

---

## 3. Consolidate the four docker-compose files
`docker-compose.yml`, `.full.yml`, `.server.yml`, `.pi.yml` duplicate nearly the whole graph.
The qdrant healthcheck fix only landed in one — that divergence caused the outage. Consider a
base compose + profiles/`extends` to avoid copy-paste.

---

## 4. De-duplicate the healthcheck one-liners
The same `urllib` healthcheck repeats across every service (lines 106, 136, 183, 222, 261, 287).
Replace with a small shared check or env-driven default.

---

## 5. Split the monolith route files
- `gateway/app/main.py` (~1,350+ lines: routing + proxying + health + voice + websockets in one file)
- `content-pipeline/app/main.py` (~1,300 lines)
- `pack-service/app/main.py`, `experiment-service`

Move routing/services into `app/services/` (already started with `experiment_service_client.py`).

---

## 6. Standardize configuration across services
Only `gateway` uses `shared/config.py` (Pydantic typed settings). The large services read
`os.environ` directly with `${VAR:-default}` fallbacks repeated in compose. Adopt the
`shared/config.py` pattern everywhere to remove fallback-default duplication.

---

## 7. Standardize `/health` endpoints
Health routes are inconsistent:
- `gateway` → `HealthResponse`
- `content-pipeline` → `HealthResponse`
- `pack-service/app/main.py:72`, `experiment-service/app/main.py:46` → bare `dict[str,str]`

Align them so compose healthchecks report richer status.

---

### Priority
1. (DONE) → #2 voice-service restored & gated behind `VOICE_SERVICE_ENABLED`
2. (logical/effort) → #1 teacher/admin ingestion path
3. (maintenance) → #3, #4 compose consolidation / DRY
4. (refactor) → #5, #6, #7 structure & cleanliness