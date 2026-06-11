# OpenAPI Generation

Run the service:

```bash
cd backend/voice-service
uvicorn app:app --host 0.0.0.0 --port 8050
```

Export OpenAPI:

```bash
curl http://localhost:8050/openapi.json > backend/voice-service/docs/openapi.json
```

The OpenAPI contract includes:

- `POST /voice/query`
- `POST /voice/tts`
- `POST /voice/stt`
- `GET /voice/audio/{asset_id}`
- `GET /audio/{asset_id}`
- `GET /voice/metrics`
- `GET /health`
