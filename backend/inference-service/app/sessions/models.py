from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


class ConversationSession(BaseModel):
    session_id: str
    student_id: str | None = None
    language: str | None = None
    grade: int | None = None
    subject: str | None = None
    chapter_id: str | None = None
    experiment_id: str | None = None
    chat_history: list[dict[str, Any]] = Field(default_factory=list)
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)
