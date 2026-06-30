from __future__ import annotations

import io
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tts.mock import MockTTSEngine  # noqa: E402


def test_mock_tts_generates_audible_wav() -> None:
    engine = MockTTSEngine()
    audio = _run(engine.synthesize("Hello voice", "default", "en", "wav"))
    assert audio.startswith(b"RIFF")

    with wave.open(io.BytesIO(audio), "rb") as wav:
        frames = wav.getnframes()
        data = wav.readframes(frames)
        assert frames > 0
        assert any(byte != 0 for byte in data)


def _run(coro):
    try:
        import asyncio

        return asyncio.run(coro)
    except RuntimeError:
        import asyncio

        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
