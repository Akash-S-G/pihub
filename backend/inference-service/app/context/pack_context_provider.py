from __future__ import annotations

import time
from typing import Any, Awaitable, Callable

from .models import TutorContext


RetrieveContextFn = Callable[[Any], Awaitable[tuple[list[Any], dict[str, Any]]]]


class PackContextProvider:
    """Provides curriculum context through the existing RAG retrieval path."""

    def __init__(self, retrieve_context: RetrieveContextFn) -> None:
        self.retrieve_context = retrieve_context

    async def load(self, request: Any) -> tuple[TutorContext, float]:
        started = time.perf_counter()
        context, diagnostics = await self.retrieve_context(request)
        # The current RAG service returns chapter-level text chunks. Other fields
        # are explicit extension points for pack-backed assets as they mature.
        tutor_context = TutorContext(
            chapter=context,
            concepts=self._asset_context_by_type(request, "concept"),
            glossary=self._asset_context_by_type(request, "glossary"),
            faq=self._asset_context_by_type(request, "faq"),
            learning_objectives=self._asset_context_by_type(request, "learning_objective"),
            retrieval_diagnostics=diagnostics,
        )
        return tutor_context, (time.perf_counter() - started) * 1000

    @staticmethod
    def _asset_context_by_type(request: Any, source_type: str) -> list[dict[str, Any]]:
        assets = getattr(request, "asset_context", []) or []
        return [item for item in assets if isinstance(item, dict) and str(item.get("source_type") or "").lower() == source_type]
