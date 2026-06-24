from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any
from stt.base import STTEngine
from tts.base import TTSEngine


class TutorEngine(ABC):
    @abstractmethod
    async def answer_with_context(self, question: str, filters: dict[str, Any]) -> dict[str, Any]:
        """Gemma 4 12B tutor over curriculum RAG. Must return no answer without context."""

    @abstractmethod
    async def stream_answer_with_context(self, question: str, filters: dict[str, Any]) -> AsyncIterator[str]:
        """Streaming tutor answer chunks over curriculum RAG."""
