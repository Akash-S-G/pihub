import asyncio
import json
import base64
import time
import io
import websockets
from gtts import gTTS
import os

GATEWAY_WS_URL = "ws://127.0.0.1/voice/stream"

LANGUAGES = [
    {"code": "en", "text": "What is photosynthesis?"},
    {"code": "hi", "text": "प्रकाश संश्लेषण क्या है?"},
    {"code": "kn", "text": "ಪ್ರಕಾಶಸಂಶ್ಲೇಷಣೆ ಎಂದರೇನು?"}
]

def generate_audio(text, lang):
    tts = gTTS(text, lang=lang)
    fp = io.BytesIO()
    tts.write_to_fp(fp)
    fp.seek(0)
    return fp.read()

async def test_language(lang_info):
    lang_code = lang_info["code"]
    text = lang_info["text"]
    print(f"\n--- Testing Language: {lang_code.upper()} ---")
    print(f"Generating TTS for: {text}")
    
    audio_bytes = generate_audio(text, lang_code)
    print(f"Generated {len(audio_bytes)} bytes of audio.")

    session_id = f"audit-{lang_code}-{int(time.time())}"
    
    try:
        async with websockets.connect(GATEWAY_WS_URL) as ws:
            print(f"Connected to WS for {lang_code}")
            
            # Start session
            await ws.send(json.dumps({
                "type": "session_start",
                "session_id": session_id,
                "language": lang_code
            }))
            
            resp = json.loads(await ws.recv())
            print(f"Received: {resp}")
            assert resp["type"] == "session_acknowledged"
            
            # Send chunks (send it all in one chunk for simplicity)
            chunk_b64 = base64.b64encode(audio_bytes).decode('utf-8')
            await ws.send(json.dumps({
                "type": "audio_chunk",
                "sequence": 1,
                "data": chunk_b64
            }))
            
            # Complete
            await ws.send(json.dumps({
                "type": "audio_complete"
            }))
            
            # Expect transcribing
            resp = json.loads(await ws.recv())
            print(f"Received: {resp}")
            assert resp["type"] == "transcribing"
            
            # Expect thinking (STT done)
            stt_start = time.time()
            resp = json.loads(await ws.recv())
            print(f"Received: {resp} (took {time.time() - stt_start:.2f}s)")
            
            # If STT failed or threw an error, it might not be thinking.
            # But according to our routes.py, it sends thinking AFTER STT.
            if resp.get("type") == "error":
                print(f"[FAIL] Error from server: {resp}")
                return False
                
            assert resp["type"] == "thinking"
            
            # Now we expect TTS stage: generating_audio
            resp = json.loads(await ws.recv())
            print(f"Received: {resp}")
            assert resp["type"] == "generating_audio"
            
            # Now we expect audio_chunks and then audio_complete
            chunks_received = 0
            while True:
                resp = json.loads(await ws.recv())
                if resp["type"] == "audio_chunk":
                    chunks_received += 1
                elif resp["type"] == "audio_complete":
                    print(f"Received audio_complete. Total chunks: {chunks_received}")
                    print(f"Final reported language from tutor/TTS: {resp.get('language')}")
                    assert resp.get("language") == lang_code, f"Expected {lang_code}, got {resp.get('language')}"
                    break
                else:
                    print(f"Unexpected message: {resp}")
                    
            print(f"[PASS] {lang_code.upper()} test completed successfully.")
            return True

    except Exception as e:
        print(f"[FAIL] Exception during test for {lang_code}: {e}")
        return False

async def run_audit():
    print("Starting Multilingual Real STT Audit...")
    success = True
    for lang in LANGUAGES:
        res = await test_language(lang)
        if not res:
            success = False
            
    if success:
        print("\n\nAll Real STT and Multilingual Flow Audits PASSED!")
    else:
        print("\n\nSome audits FAILED.")

if __name__ == "__main__":
    asyncio.run(run_audit())
