from __future__ import annotations

import os

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.errors import error_payload


DEFAULT_LIMITS = {
    "manifest": 512 * 1024,
    "share_package": 2 * 1024 * 1024,
    "submission": 2 * 1024 * 1024,
    "ai": 256 * 1024,
}

ENV_LIMITS = {
    "manifest": ("MAX_MANIFEST_SIZE", "EXPERIMENT_MANIFEST_MAX_BYTES"),
    "share_package": ("MAX_SHARE_PACKAGE_SIZE", "EXPERIMENT_SHARE_PACKAGE_MAX_BYTES"),
    "submission": ("MAX_SUBMISSION_SIZE", "EXPERIMENT_SUBMISSION_MAX_BYTES"),
    "ai": ("MAX_AI_REQUEST_SIZE", "EXPERIMENT_AI_MAX_BYTES"),
}


def _limit(name: str) -> int:
    for env_name in ENV_LIMITS[name]:
        raw_value = os.getenv(env_name)
        if raw_value:
            return int(raw_value)
    return DEFAULT_LIMITS[name]


def limit_for_path(path: str) -> int | None:
    if path.startswith("/ai/"):
        return _limit("ai")
    if path.startswith("/sharing/"):
        return _limit("share_package")
    if "/submit" in path or path.startswith("/classroom/"):
        return _limit("submission")
    if path.startswith("/builder/") or path.startswith("/manifest/"):
        return _limit("manifest")
    return None


async def payload_limit_middleware(request: Request, call_next):
    limit = limit_for_path(request.url.path)
    if limit is None:
        return await call_next(request)
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > limit:
        return JSONResponse(status_code=413, content=error_payload("payload_too_large", f"Payload exceeds {limit} bytes"))
    body = await request.body()
    if len(body) > limit:
        return JSONResponse(status_code=413, content=error_payload("payload_too_large", f"Payload exceeds {limit} bytes"))
    return await call_next(request)
