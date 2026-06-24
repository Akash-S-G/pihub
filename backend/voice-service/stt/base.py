from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

@dataclass
class Transcript:
    text: str
    language: str
    confidence: float
    latency_ms: float

class STTEngine(ABC):
    @abstractmethod
    async def transcribe(self, audio: bytes, language: str | None = None) -> Transcript:
        """Speech to text interface."""
