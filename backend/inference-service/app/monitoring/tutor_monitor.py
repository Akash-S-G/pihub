from __future__ import annotations

from pydantic import BaseModel


class TutorLatencyBreakdown(BaseModel):
    tutor_latency_ms: float = 0.0
    context_latency_ms: float = 0.0
    language_adapter_latency_ms: float = 0.0
    total_response_latency_ms: float = 0.0
