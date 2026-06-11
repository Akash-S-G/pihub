from __future__ import annotations

import logging
import json
import time
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator
from uuid import uuid4

from fastapi import Request


logger = logging.getLogger("experiment-service.request")
operation_logger = logging.getLogger("experiment-service.operation")
slow_query_logger = logging.getLogger("experiment-service.slow_query")
request_id_var: ContextVar[str] = ContextVar("request_id", default="")
SLOW_QUERY_THRESHOLD_MS = 100.0


async def request_observability_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid4())
    request_id_var.set(request_id)
    request.state.request_id = request_id
    start = time.perf_counter()
    logger.info("[REQUEST] start request_id=%s method=%s path=%s", request_id, request.method, request.url.path)
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.exception("[REQUEST] error request_id=%s duration_ms=%s", request_id, duration_ms)
        raise
    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    response.headers["x-request-id"] = request_id
    logger.info(
        "[REQUEST] end request_id=%s method=%s path=%s status=%s duration_ms=%s",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


def current_request_id() -> str:
    return request_id_var.get() or str(uuid4())


def structured_log(
    operation: str,
    *,
    status: str,
    request_id: str | None = None,
    manifest_id: str | None = None,
    revision: int | None = None,
    duration_ms: float | None = None,
    error_code: str | None = None,
    **extra: Any,
) -> None:
    payload: dict[str, Any] = {
        "request_id": request_id or current_request_id(),
        "operation": operation,
        "status": status,
    }
    if manifest_id is not None:
        payload["manifest_id"] = manifest_id
    if revision is not None:
        payload["revision"] = revision
    if duration_ms is not None:
        payload["duration_ms"] = round(duration_ms, 2)
    if error_code is not None:
        payload["error_code"] = error_code
    payload.update({key: value for key, value in extra.items() if value is not None})
    operation_logger.info(json.dumps(payload, sort_keys=True, separators=(",", ":")))


@contextmanager
def operation_span(operation: str, **fields: Any) -> Iterator[None]:
    start = time.perf_counter()
    try:
        yield
    except Exception as exc:
        structured_log(
            operation,
            status="error",
            duration_ms=(time.perf_counter() - start) * 1000,
            error_code=exc.__class__.__name__,
            **fields,
        )
        raise
    structured_log(operation, status="success", duration_ms=(time.perf_counter() - start) * 1000, **fields)


def log_slow_query(table: str, operation: str, duration_ms: float) -> None:
    if duration_ms <= SLOW_QUERY_THRESHOLD_MS:
        return
    slow_query_logger.warning(
        "[SLOW_QUERY] %s",
        json.dumps(
            {
                "table": table,
                "operation": operation,
                "duration_ms": round(duration_ms, 2),
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
    )
