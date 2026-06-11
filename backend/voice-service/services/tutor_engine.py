from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from services.errors import not_configured
from services.interfaces import TutorEngine


class RagTutorEngine(TutorEngine):
    """Gemma 4 12B llama.cpp tutor over curriculum RAG boundary."""

    async def answer_with_context(self, question: str, filters: dict[str, Any]) -> dict[str, Any]:
        raise not_configured("Gemma 4 12B curriculum RAG tutor")

    async def stream_answer_with_context(self, question: str, filters: dict[str, Any]) -> AsyncIterator[str]:
        raise not_configured("Gemma 4 12B streaming curriculum RAG tutor")
        yield ""
