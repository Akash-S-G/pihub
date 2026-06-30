from __future__ import annotations

import asyncio
import io
import math
import wave
from array import array
from collections.abc import AsyncIterator
from .base import TTSEngine

class MockTTSEngine(TTSEngine):
    """Fallback TTS implementation that generates an audible synthetic voice."""

    def __init__(self) -> None:
        self.sample_rate = 22050

    async def synthesize(self, text: str, voice: str, language: str, audio_format: str) -> bytes:
        return self._render_wav(text, voice, language)

    async def health_check(self) -> dict[str, object]:
        return {
            "provider": "mock_tone",
            "loaded": True,
            "status": "fallback_ready",
            "sample_rate": self.sample_rate,
        }

    async def stream(self, text: str, voice: str, language: str, audio_format: str) -> AsyncIterator[bytes]:
        audio = self._render_wav(text, voice, language)
        for offset in range(0, len(audio), 8192):
            await asyncio.sleep(0.005)
            yield audio[offset : offset + 8192]

    def _render_wav(self, text: str, voice: str, language: str) -> bytes:
        samples = self._render_samples(text or "voice")
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(self.sample_rate)
            wav.writeframes(samples.tobytes())
        return buffer.getvalue()

    def _render_samples(self, text: str) -> array:
        waveform = array("h")
        chars = [ch for ch in text if not ch.isspace()]
        if not chars:
            chars = ["v"]
        for index, ch in enumerate(chars):
            base_freq = 170 + (ord(ch.lower()) % 32) * 18
            duration = 0.075 + (index % 4) * 0.01
            frame_count = int(self.sample_rate * duration)
            for n in range(frame_count):
                phase = n / self.sample_rate
                attack = min(1.0, n / max(1, frame_count * 0.12))
                release = min(1.0, (frame_count - n) / max(1, frame_count * 0.18))
                envelope = max(0.0, min(attack, release))
                carrier = (
                    0.65 * math.sin(2 * math.pi * base_freq * phase)
                    + 0.25 * math.sin(2 * math.pi * base_freq * 2 * phase)
                    + 0.10 * math.sin(2 * math.pi * base_freq * 3 * phase)
                )
                sample = int(14000 * envelope * carrier)
                waveform.append(max(-32768, min(32767, sample)))
            pause = int(self.sample_rate * 0.018)
            waveform.extend([0] * pause)
        return waveform
