"""MinIO/S3-compatible audio storage."""

from __future__ import annotations

import hashlib
import os
from io import BytesIO
from typing import Any

from audio import AudioObject, AudioStorage


class MinIOAudioStorage(AudioStorage):
    """Production audio storage using MinIO (S3-compatible)."""

    def __init__(
        self,
        endpoint: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        bucket: str = "idp-voice-audio",
        secure: bool = False,
        region: str = "us-east-1",
    ) -> None:
        self.endpoint = endpoint or os.getenv("MINIO_ENDPOINT", "localhost:9000")
        self.access_key = access_key or os.getenv("MINIO_ACCESS_KEY", "minioadmin")
        self.secret_key = secret_key or os.getenv("MINIO_SECRET_KEY", "minioadmin")
        self.bucket = bucket or os.getenv("MINIO_BUCKET", "idp-voice-audio")
        self.secure = secure
        self.region = region
        self._client: Any = None
        self._inited = False

    async def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            from minio import Minio  # type: ignore[import-untyped]
            client = Minio(
                self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=self.secure,
                region=self.region,
            )
            self._client = client
            return client
        except ImportError as exc:
            raise RuntimeError("minio package required") from exc

    async def get(self, asset_id: str) -> AudioObject | None:
        client = await self._ensure_client()
        key = self._object_name(asset_id)
        try:
            response = client.get_object(self.bucket, key)
            content = response.read()
            checksum = hashlib.sha256(content).hexdigest()
            return AudioObject(
                asset_id=asset_id,
                content=content,
                content_type="audio/wav",
                checksum=checksum,
            )
        except Exception:
            return None

    async def put(self, asset_id: str, content: bytes, content_type: str = "audio/wav") -> AudioObject:
        client = await self._ensure_client()
        key = self._object_name(asset_id)
        client.put_object(self.bucket, key, BytesIO(content), len(content), content_type=content_type)
        checksum = hashlib.sha256(content).hexdigest()
        return AudioObject(asset_id=asset_id, content=content, content_type=content_type, checksum=checksum)

    @staticmethod
    def _object_name(asset_id: str) -> str:
        return f"audio/{asset_id.replace('/', '_')}".lstrip("/")
