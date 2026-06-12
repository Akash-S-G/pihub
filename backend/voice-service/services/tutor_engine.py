from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from typing import Any

import httpx

from services.interfaces import TutorEngine


class RagTutorEngine(TutorEngine):
    """HTTP adapter for the existing curriculum tutor pipeline."""

    def __init__(self, base_url: str | None = None, path: str | None = None) -> None:
        self.base_url = (base_url or os.getenv("VOICE_TUTOR_URL") or "http://inference-service:8010").rstrip("/")
        self.path = path or os.getenv("VOICE_TUTOR_PATH") or "/ai/tutor"

    async def answer_with_context(self, question: str, filters: dict[str, Any]) -> dict[str, Any]:
        payload = self._payload(question, filters, stream=False)
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(f"{self.base_url}{self.path}", json=payload)
        response.raise_for_status()
        result = response.json()
        return {
            "answer": result.get("answer") or result.get("text") or "",
            "context": result.get("context") or result.get("sources") or [],
            "raw": result,
        }

    async def stream_answer_with_context(self, question: str, filters: dict[str, Any]) -> AsyncIterator[str]:
        payload = self._payload(question, filters, stream=True)
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", f"{self.base_url}{self.path}", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    chunk = self._stream_text(line)
                    if chunk:
                        yield chunk

    @staticmethod
    def _payload(question: str, filters: dict[str, Any], stream: bool) -> dict[str, Any]:
        return {
            "question": question,
            "grade": filters.get("grade"),
            "subject": filters.get("subject"),
            "chapter": filters.get("chapter") or filters.get("chapter_id"),
            "topic": filters.get("topic"),
            "language": filters.get("language") or "en",
            "stream": stream,
        }

    @staticmethod
    def _stream_text(line: str) -> str:
        if not line:
            return ""
        if line.startswith("data:"):
            line = line.removeprefix("data:").strip()
        if line == "[DONE]":
            return ""
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            return line
        return str(data.get("answer") or data.get("text") or data.get("delta") or data.get("content") or "")
