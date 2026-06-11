from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class CacheEntry:
    value: Any
    expires_at: float | None = None


class VoiceCache(ABC):
    @abstractmethod
    async def get(self, key: str) -> Any | None:
        """Get a cached question, answer, or audio reference."""

    @abstractmethod
    async def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        """Set a cached question, answer, or audio reference."""


class InMemoryVoiceCache(VoiceCache):
    """Development/test cache. Production can replace this with Redis."""

    def __init__(self) -> None:
        self._store: dict[str, CacheEntry] = {}

    async def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if not entry:
            return None
        if entry.expires_at is not None and entry.expires_at < time.time():
            self._store.pop(key, None)
            return None
        return entry.value

    async def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        expires_at = time.time() + ttl_seconds if ttl_seconds else None
        self._store[key] = CacheEntry(value=value, expires_at=expires_at)
