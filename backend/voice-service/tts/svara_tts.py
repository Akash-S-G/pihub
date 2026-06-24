from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

from config import get_runtime_settings
from services.errors import VoiceServiceError
from .base import TTSEngine
from .providers import SvaraLocalProvider, SvaraProviderError


class SvaraTTSEngine(TTSEngine):
    """Svara TTS engine behind the generic TTSEngine interface."""

    def __init__(self, runtime: SvaraLocalProvider | None = None) -> None:
        self.runtime = runtime or SvaraLocalProvider(get_runtime_settings())

    async def synthesize(self, text: str, voice: str, language: str, audio_format: str) -> bytes:
        result = await self._synthesize_provider(text, language)
        return Path(result.file_path).read_bytes()

    async def synthesize_result(self, text: str, voice: str, language: str, audio_format: str):
        return await self._synthesize_provider(text, language)

    async def stream(self, text: str, voice: str, language: str, audio_format: str) -> AsyncIterator[bytes]:
        async for chunk in self.runtime.synthesize_stream(text, language):
            yield chunk

    async def health_check(self) -> dict[str, object]:
        return await self.runtime.health_check()

    async def warmup(self) -> dict[str, object]:
        return await self.runtime.warmup()

    async def close(self) -> None:
        await self.runtime.close()

    async def _synthesize_provider(self, text: str, language: str):
        try:
            return await self.runtime.synthesize(text, language)
        except SvaraProviderError as exc:
            raise VoiceServiceError(exc.status_code, exc.code, exc.message) from exc
