# PIHUB Repository Audit — July 2026

Scope: full working tree on `dev` after landing the EnrichedContentAgent (commit `86fb773`)
and the educational-intelligence module set (`8d2c2f4`). Covers architecture, security,
deployment, performance, and repo hygiene, with prioritized recommendations.

---

## 1. Current state snapshot

| Area | State |
|---|---|
| Branch | `dev`, strictly ahead of `main` (fast-forward mergeable) |
| Services | qdrant, **mongo (new)**, **cobalt (new)**, inference-service, content-pipeline, gateway, pack-service, voice-service, nginx |
| New agent | `EnrichedContentAgent` → `POST /build/enriched-artifacts` (bilingual kn+en enrichment, web sims, Cobalt media download, ffmpeg compression, Mongo + Qdrant persistence) |
| Tests | `tests/test_enriched_content_agent.py` 8/8 green; live Cobalt download verified end-to-end |
| Models | `backend/voice-service/models/` (3.9 GB) now gitignored and untracked |

---

## 2. Security findings

### 2.1 HIGH — MongoDB runs without authentication
`docker-compose.yml` starts `mongo:7.0` with no `MONGO_INITDB_ROOT_USERNAME/PASSWORD`.
Anything on the compose network can read/write all media metadata.
**Fix:** set root credentials from `.env`, use a connection string with auth
(`mongodb://user:pass@mongo:27017`), and keep the port un-published (it currently is —
good). For the Pi image, enable `--auth` explicitly.

### 2.2 HIGH — Qdrant has no API key
`QDRANT__SERVICE__API_KEY` is unset. Qdrant is only `expose`d (not published) in
`docker-compose.yml`, but `docker-compose.server.yml` **publishes 6333/6334 to the host**.
Anyone who can reach the server can dump or delete every collection.
**Fix:** set `QDRANT__SERVICE__API_KEY` + pass it from clients; stop publishing 6333/6334
in the server compose (nginx or the gateway should be the only public entry).

### 2.3 MEDIUM — nginx serves plain HTTP only
`nginx.conf` listens on `:80` with no TLS and no auth on proxied API routes. Fine for a
LAN-only Pi appliance; not fine the moment it's reachable beyond the classroom LAN.
**Fix:** terminate TLS at nginx (self-signed or mkcert for offline deployments), or
document explicitly that the appliance must sit on an isolated network.

### 2.4 MEDIUM — server compose publishes internal service ports
`8001` (content-pipeline), `8010` (inference), `8050`, `6333/6334` are all host-published
in `docker-compose.server.yml`, bypassing the gateway/nginx entirely.
**Fix:** switch to `expose:` and route everything through nginx.

### 2.5 MEDIUM — SSRF surface in enrichment downloader
`MediaStore.store_image` / `WebResourceFinder` fetch arbitrary URLs discovered from web
search. A malicious search result could point at internal endpoints
(`http://qdrant:6333/...`, `http://mongo:27017`, cloud metadata IPs).
**Fix (low-effort):** in `MediaStore`/`WebResourceFinder`, reject non-http(s) schemes and
private/loopback/link-local IPs after DNS resolution; allowlist media content-types.

### 2.6 LOW — Cobalt instance is unauthenticated on the compose network
Acceptable inside the network, but if you ever publish it, enable Cobalt's `Api-Key`
auth (supported natively; add the header in `MediaStore._cobalt_download`).

### 2.7 LOW — dependency hygiene
All 18 deps in `content-pipeline/requirements.txt` are `>=` (unpinned) — builds are not
reproducible and a bad upstream release breaks the Pi image. **Fix:** pin with
`uv pip compile` (lockfile) for release builds. Also `bs4`-based DuckDuckGo HTML scraping
can silently break — treat as best-effort (already coded to degrade gracefully).

### 2.8 POSITIVE notes
- No secrets found in staged diffs (scanned before commit).
- `.env` is gitignored; only one key reference inside.
- Media store is content-addressed (blake2b of URL) — no path-traversal from titles.
- All external calls (web search, Cobalt, Mongo, Qdrant) degrade gracefully offline.

---

## 3. Deployment findings

### 3.1 No healthchecks (1 total across both compose files)
Services race on startup (content-pipeline can beat Qdrant/Mongo up).
**Fix:** add `healthcheck:` blocks (`curl -f localhost:6333/readyz`, `mongosh --eval
'db.adminCommand("ping")'`, Cobalt `GET /`) and use `depends_on: {condition:
service_healthy}`.

### 3.2 No resource limits
No `mem_limit`/`cpus` anywhere. On an 8 GB Pi, one runaway ffmpeg encode or model load
can OOM the whole appliance. **Fix:** `mem_limit` per service; cap ffmpeg with
`-threads 2` on Pi builds.

### 3.3 Cobalt/Mongo only needed at build time
The Pi serves pre-baked packs; it never downloads videos. **Fix:** use compose profiles —
`profiles: ["build"]` on cobalt (and optionally mongo if you snapshot to a dump) so the
Pi runtime footprint stays minimal.

### 3.4 Media volume growth is unbounded
`/shared/media` grows with every enrichment run. **Fix:** add a size budget
(e.g. `MEDIA_MAX_TOTAL_GB`) checked in `MediaStore` before download, plus an admin
endpoint to list/prune by subject.

### 3.5 ffmpeg must exist in the content-pipeline image
Compression falls back to storing the raw file if ffmpeg is missing (graceful but larger
files). **Fix:** `apt-get install -y ffmpeg` in `content-pipeline/Dockerfile` — small,
and CRF-28 H.264 typically cuts YouTube 480p by 40–60%.

---

## 4. Performance / architecture observations

1. **Per-topic enrichment is already concurrent** (asyncio.gather) — good. But Cobalt
   downloads inside it are serialized per topic via `asyncio.to_thread`; a global
   `asyncio.Semaphore(2)` around `store_video` would bound bandwidth + CPU on the host.
2. **Embedding model reuse** — `EnrichmentStore` shares the pipeline's
   sentence-transformer (no second model in RAM). Keep it that way.
3. **DuckDuckGo scraping fragility** — the finder's only true web-search backend. A
   pluggable provider (SearxNG container fits the self-hosted philosophy; Brave/Tavily
   need keys) would remove the single point of failure. The interface is already isolated
   in `_duckduckgo_search`, so it's a drop-in.
4. **Topic dedup state is in-process** (`_seen_topics_by_subject` dict) — resets on
   container restart. If cross-restart dedup matters, persist the seen-set to Mongo
   (one small collection, keyed by subject).
5. **Chunker improvements landed** (sentence-aware splits, noise stripping) — retrieval
   quality should be re-benchmarked against the pre-change Qdrant snapshot before
   re-ingesting all textbooks.
6. **`simulation_matcher.py` removed**; PhET local catalog + EnrichmentRouter remain the
   offline sim path, web sims are additive. No conflict.

---

## 5. Repo hygiene (done in this audit)

- ✅ `backend/voice-service/models/` (3.9 GB gemma4_audio HF cache) added to `.gitignore`
  and **untracked** via `git rm -r --cached` (17 files removed from the index; files kept
  on disk).
- ✅ Local debug scratch ignored: `backend/.local_run/`, `backend/.local_run_env`,
  `backend/_depcheck.py`, `backend/content-pipeline/_dbgpath.py`.
- ✅ All remaining working-tree changes committed on `dev` (`8d2c2f4`): full
  `educational_intelligence` package now tracked (orchestrator, generators, inference
  client, image extractor, reports renderer), chunker improvements, ingest/vector-store
  updates, nginx + server-compose updates.
- ⚠️ Note: 3.9 GB of model blobs still exist in **git history** (earlier commits). Clone
  size stays large until history is rewritten (`git filter-repo`) — only worth doing
  before the repo is shared/pushed anywhere new, and it rewrites SHAs.

---

## 6. Prioritized action list

| # | Action | Effort | Impact |
|---|---|---|---|
| 1 | Mongo auth + Qdrant API key | S | HIGH (security) |
| 2 | Stop publishing 6333/8001/8010 in server compose; route via nginx | S | HIGH |
| 3 | Healthchecks + `service_healthy` dependencies | S | HIGH (reliability) |
| 4 | ffmpeg in content-pipeline Dockerfile | XS | HIGH (media size) |
| 5 | SSRF guard in MediaStore/WebResourceFinder | S | MED |
| 6 | Compose `build` profile for cobalt | XS | MED (Pi footprint) |
| 7 | Pin/lock requirements for release images | S | MED |
| 8 | Media size budget + prune endpoint | M | MED |
| 9 | Download semaphore (bound concurrent Cobalt fetches) | XS | MED |
| 10 | Pluggable search provider (SearxNG) | M | LOW-MED |
| 11 | TLS on nginx (or documented LAN-only constraint) | M | LOW (LAN) / HIGH (WAN) |
| 12 | History rewrite to purge model blobs (optional, pre-share only) | M | LOW |
