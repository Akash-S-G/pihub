"""Production Redis cache."""

from __future__ import annotations

import json
import os
from typing import Any

from cache import VoiceCache


class RedisVoiceCache(VoiceCache):
    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        db: int = 0,
        password: str | None = None,
        key_prefix: str = "idp:voice:",
    ) -> None:
        self._host = host or os.getenv("REDIS_HOST") or "localhost"
        self._port = port or int(os.getenv("REDIS_PORT", "6379"))
        self._password = password or os.getenv("REDIS_PASSWORD") or None
        self._db = db
        self._prefix = key_prefix
        self._client: Any = None
        self._connected = False
        try:
            import redis.asyncio as aioredis  # type: ignore[import]

            self._client = aioredis.Redis(
                host=self._host,
                port=self._port,
                password=self._password,
                db=self._db,
                decode_responses=False,
                socket_connect_timeout=2,
                socket_timeout=2,
                health_check_interval=30,
            )
            self._connected = True
        except ImportError:
            pass
        except Exception:
            self._client = None

    async def get(self, key: str) -> Any | None:
        if not self._connected or self._client is None:
            return None
        try:
            data = await self._client.get(f"{self._prefix}{key}")
            if data is None:
                return None
            return json.loads(data.decode("utf-8"))
        except Exception:
            return None

    async def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        if not self._connected or self._client is None:
            return
        try:
            data = json.dumps(value, default=str).encode("utf-8")
            if ttl_seconds:
                await self._client.setex(f"{self._prefix}{key}", ttl_seconds, data)
            else:
                await self._client.set(f"{self._prefix}{key}", data)
        except Exception:
            pass
