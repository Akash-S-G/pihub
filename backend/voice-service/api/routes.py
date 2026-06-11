from __future__ import annotations

from fastapi import APIRouter, File, Header, HTTPException, Request, UploadFile
from fastapi.responses import Response, StreamingResponse

from models import STTRequest, STTResponse, TTSRequest, TTSResponse, VoiceQueryRequest, VoiceQueryResponse

router = APIRouter()


@router.post("/voice/query", response_model=VoiceQueryResponse, tags=["voice"])
async def voice_query(request: Request, payload: VoiceQueryRequest) -> VoiceQueryResponse:
    gateway = request.app.state.voice_gateway
    return await gateway.query(payload)


@router.post("/voice/tts", response_model=TTSResponse, tags=["voice"])
async def voice_tts(request: Request, payload: TTSRequest) -> TTSResponse | StreamingResponse:
    gateway = request.app.state.voice_gateway
    if payload.stream:
        streamer = request.app.state.voice_streamer
        return StreamingResponse(streamer.tts.stream(payload.text, payload.voice, payload.language, payload.format), media_type=f"audio/{payload.format}")
    return await gateway.tts_only(payload)


@router.post("/voice/stt", response_model=STTResponse, tags=["voice"])
async def voice_stt(
    request: Request,
    language: str | None = None,
    enable_partial_transcripts: bool = False,
    file: UploadFile = File(...),
) -> STTResponse:
    request.app.state.voice_metrics.increment("stt_requests")
    audio = await file.read()
    result = await request.app.state.stt_engine.transcribe(audio, language)
    return STTResponse(
        transcript=str(result.get("transcript") or ""),
        language=str(result.get("language") or language or "unknown"),
        partial_transcripts=list(result.get("partial_transcripts") or []) if enable_partial_transcripts else [],
        confidence=result.get("confidence"),
        metrics=dict(result.get("metrics") or {}),
    )


@router.get("/voice/audio/{asset_id}", tags=["voice", "audio"])
@router.get("/audio/{asset_id}", tags=["audio"])
async def get_audio_asset(request: Request, asset_id: str, range_header: str | None = Header(default=None, alias="Range")) -> Response:
    storage = request.app.state.audio_storage
    audio = await storage.get(asset_id)
    if not audio:
        raise HTTPException(status_code=404, detail={"success": False, "error": {"code": "AUDIO_NOT_FOUND", "message": asset_id}})
    content = audio.content
    headers = {
        "Accept-Ranges": "bytes",
        "Cache-Control": "public, max-age=3600",
        "ETag": audio.checksum or "",
    }
    if range_header:
        start, end = _parse_range(range_header, len(content))
        headers["Content-Range"] = f"bytes {start}-{end}/{len(content)}"
        return Response(content[start : end + 1], status_code=206, media_type=audio.content_type, headers=headers)
    headers["Content-Length"] = str(len(content))
    return Response(content, media_type=audio.content_type, headers=headers)


@router.get("/voice/metrics", tags=["voice", "analytics"])
async def voice_metrics(request: Request) -> dict[str, object]:
    return request.app.state.voice_metrics.snapshot()


def _parse_range(header: str, size: int) -> tuple[int, int]:
    if not header.startswith("bytes="):
        raise HTTPException(status_code=416, detail="Only bytes ranges are supported")
    raw_start, _, raw_end = header.removeprefix("bytes=").partition("-")
    start = int(raw_start or 0)
    end = int(raw_end) if raw_end else size - 1
    if start < 0 or end < start or start >= size:
        raise HTTPException(status_code=416, detail="Invalid range")
    return start, min(end, size - 1)
