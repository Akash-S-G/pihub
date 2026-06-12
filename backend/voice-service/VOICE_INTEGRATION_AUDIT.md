# Voice Integration Audit

Status: COMPLETED

## Scope Audited

```text
backend/docker-compose.yml
backend/gateway/
backend/nginx/
backend/inference-service/
backend/pihub/
frontend/
```

## Existing Service Discovery

The gateway exposes:

```text
GET /discovery
GET /discovery/beacon
UDP broadcast beacon on port 47890
```

Discovery payload is built in:

```text
backend/gateway/app/main.py
```

Existing capabilities before this integration included:

```text
rag
sync
assets
streaming
planner
progress
metrics
experiments
```

Voice was not advertised before this sprint.

## Existing Gateway Routing Strategy

Gateway routing is implemented directly in:

```text
backend/gateway/app/main.py
```

Patterns found:

```text
Client route
  -> gateway endpoint
  -> _get_json / _post_json / _proxy_to / _proxy_stream
  -> internal service URL from shared settings
```

Examples:

```text
/ai/tutor -> inference-service
/packs/* -> pack-service / pihub
/experiments/* -> experiment-service
/api/v1/pdf/* -> pack-service
```

Before this sprint there were no voice routes in the gateway.

## Existing Nginx Routing Strategy

Nginx routes all external traffic to the gateway:

```text
Client
  -> nginx
  -> gateway:8000
```

File:

```text
backend/nginx/nginx.conf
```

There was no direct routing to internal services. This is the correct pattern for voice integration.

## Existing Authentication Flow

Gateway public educational endpoints do not currently enforce a shared authentication dependency.

PiHub node has admin/device-token protected operational endpoints:

```text
X-PIHUB-Token
X-Device-Token
```

Files:

```text
backend/pihub/api/main.py
```

Because no gateway-level authentication dependency exists, voice endpoints follow the same gateway security posture as current tutor/content APIs. No separate auth system should be introduced for voice.

## Existing API Versioning Strategy

The backend uses mixed route families:

```text
/ai/*
/packs/*
/experiments/*
/api/v1/pdf/*
```

PDF APIs are versioned under `/api/v1`.

Voice integration uses:

```text
/api/voice/*
```

This matches the requested contract and keeps voice separated from existing tutor and pack routes.

## Existing Frontend API Access Pattern

No frontend directory exists in this checkout. The previous frontend references are not available on disk for direct audit.

Observed implication:

```text
Frontend contract must be generated as documentation.
Implementation cannot be validated against Flutter source in this workspace.
```

## Existing Inference/Tutor Integration

Existing tutor pipeline:

```text
Gateway /ai/tutor
  -> asset enrichment / planner routing
  -> inference-service /ai/tutor
```

Voice service previously had a `RagTutorEngine` boundary that returned `501 Not Implemented`.

## Integration Conclusion

Required integration points:

```text
docker-compose: add voice-service
gateway settings: add VOICE_SERVICE_URL
gateway routes: add /api/voice/*
gateway health/discovery: advertise voice
nginx: route /api/voice/* to gateway
voice-service tutor boundary: consume existing tutor service over HTTP
frontend: document contract
```
