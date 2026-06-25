import asyncio
import websockets
import json
import urllib.request
import base64
import time

def get_audio(text, language="en"):
    req = urllib.request.Request(
        "http://127.0.0.1:80/api/voice/tts",
        data=json.dumps({"text": text, "language": language}).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
        audio_url = data["audio_url"]
        
    audio_path = audio_url.replace("/voice/audio/", "/api/voice/audio/")
    req2 = urllib.request.Request("http://127.0.0.1:80" + audio_path)
    with urllib.request.urlopen(req2) as resp2:
        return resp2.read()

async def run_session(text, language="en", sim_context=None, expect_source=None):
    print(f"\n--- Testing: {text} ({language}) ---")
    audio_bytes = get_audio(text, language)
    chunk_size = 4096
    
    uri = "ws://127.0.0.1:80/api/v1/voice/stream"
    async with websockets.connect(uri) as ws:
        # Start
        start_payload = {
            "type": "session_start",
            "session_id": f"test_{int(time.time())}",
            "language": language
        }
        await ws.send(json.dumps(start_payload))
        
        # Stream audio
        for i in range(0, len(audio_bytes), chunk_size):
            chunk = audio_bytes[i:i+chunk_size]
            await ws.send(json.dumps({
                "type": "audio_chunk",
                "data": base64.b64encode(chunk).decode('utf-8')
            }))
            await asyncio.sleep(0.01) # Simulate real-time
            
        complete_payload = {"type": "audio_complete"}
        if sim_context:
            complete_payload["simulation_context"] = sim_context
        await ws.send(json.dumps(complete_payload))
        
        # Collect responses
        transcript = ""
        response_text = ""
        
        while True:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=20.0)
                if isinstance(msg, bytes):
                    continue # audio output chunk
                data = json.loads(msg)
                
                if data["type"] == "transcript":
                    transcript = data.get("text", "")
                    print(f"[STT] {transcript}")
                
                elif data["type"] == "response_chunk":
                    response_text += data.get("text", "")
                    
                elif data["type"] == "response_complete":
                    print(f"[Tutor] {response_text}")
                    break
                    
                elif data["type"] == "error":
                    print(f"[Error] {data.get('message')}")
                    break
                    
            except asyncio.TimeoutError:
                print("Timeout waiting for response!")
                break

async def main():
    # Phase 3 & 4: English, Hindi, Kannada
    await run_session("What is photosynthesis?", "en")
    await run_session("प्रकाश संश्लेषण क्या है?", "hi")
    await run_session("ಪ್ರಕಾಶಸಂಶ್ಲೇಷಣೆ ಎಂದರೇನು?", "kn")
    
    # Phase 5: Generated Pack Retrieval
    await run_session("What is force?", "en")
    
    # Phase 7: Simulation Context
    sim_ctx = {"id": "pendulum", "state": {"length": 2.0, "angle": 30}}
    await run_session("What is the length of this pendulum?", "en", sim_context=sim_ctx)

asyncio.run(main())
