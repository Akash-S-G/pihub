from __future__ import annotations

import asyncio
import base64
import io
import json
import wave

import httpx
import websockets


VOICE_TEXT = "ನಮಸ್ಕಾರ, ನಾನು ಪರೀಕ್ಷೆ ಮಾಡುತ್ತಿದ್ದೇನೆ."
TTS_URL = "http://voice-service:8050/voice/tts"
WS_URL = "ws://voice-service:8050/voice/stream"


async def fetch_tts_wav_bytes() -> tuple[bytes, int]:
    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST",
            TTS_URL,
            json={"text": VOICE_TEXT, "language": "kn", "stream": True, "format": "wav"},
        ) as response:
            response.raise_for_status()
            pcm = bytearray()
            async for chunk in response.aiter_bytes():
                if chunk:
                    pcm.extend(chunk)

    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(24000)
        wav_file.writeframes(bytes(pcm))
    return wav_buffer.getvalue(), len(pcm)


async def main() -> None:
    wav_bytes, pcm_len = await fetch_tts_wav_bytes()
    print(f"TTS_PCM_BYTES={pcm_len}")
    print(f"TTS_WAV_BYTES={len(wav_bytes)}")

    async with websockets.connect(WS_URL, max_size=50 * 1024 * 1024) as websocket:
        await websocket.send(json.dumps({
            "type": "session_start",
            "session_id": "kn-smoke",
            "language": "kn",
        }))
        print("WS_RECV", await websocket.recv())

        await websocket.send(json.dumps({
            "type": "audio_chunk",
            "data": base64.b64encode(wav_bytes).decode("utf-8"),
        }))
        await websocket.send(json.dumps({
            "type": "audio_complete",
            "language": "kn",
        }))

        while True:
            message = await websocket.recv()
            print("WS_RECV", message)
            payload = json.loads(message)
            if payload.get("type") == "audio_complete":
                break


if __name__ == "__main__":
    asyncio.run(main())
