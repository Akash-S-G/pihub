from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from services.interfaces import TTSEngine, TutorEngine


class VoiceStreamer:
    """Gemma stream -> text chunk -> TTS chunk -> audio chunk."""

    def __init__(self, tutor: TutorEngine, tts: TTSEngine) -> None:
        self.tutor = tutor
        self.tts = tts

    async def stream_voice_answer(
        self,
        question: str,
        filters: dict[str, Any],
        voice: str = "default",
        language: str = "en",
        audio_format: str = "wav",
    ) -> AsyncIterator[bytes]:
        async for text_chunk in self.tutor.stream_answer_with_context(question, filters):
            if not text_chunk.strip():
                continue
            async for audio_chunk in self.tts.stream(text_chunk, voice, language, audio_format):
                yield audio_chunk
