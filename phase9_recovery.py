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

async def run_recovery():
    print("--- Phase 9: Recovery Testing ---")
    audio_bytes = get_audio("What happens if the service crashes while I'm talking?", "en")
    uri = "ws://127.0.0.1:80/api/v1/voice/stream"
    try:
        async with websockets.connect(uri) as ws:
            await ws.send(json.dumps({
                "type": "session_start",
                "session_id": f"rec_{int(time.time())}",
                "language": "en"
            }))
            
            chunk_size = 4096
            mid = len(audio_bytes) // 2
            
            print("Sending first half of audio...")
            for i in range(0, mid, chunk_size):
                chunk = audio_bytes[i:i+chunk_size]
                await ws.send(json.dumps({
                    "type": "audio_chunk",
                    "data": base64.b64encode(chunk).decode('utf-8')
                }))
                await asyncio.sleep(0.01)
                
            print("Waiting for external restart to happen... Please restart inference-service now!")
            await asyncio.sleep(10)
            
            print("Sending second half of audio...")
            for i in range(mid, len(audio_bytes), chunk_size):
                chunk = audio_bytes[i:i+chunk_size]
                await ws.send(json.dumps({
                    "type": "audio_chunk",
                    "data": base64.b64encode(chunk).decode('utf-8')
                }))
                await asyncio.sleep(0.01)
                
            await ws.send(json.dumps({"type": "audio_complete"}))
            
            while True:
                msg = await asyncio.wait_for(ws.recv(), timeout=60.0)
                if isinstance(msg, bytes):
                    continue
                data = json.loads(msg)
                print("Received:", data["type"])
                if data["type"] == "error":
                    print("Error message:", data.get("message"))
                    return
                elif data["type"] == "response_complete":
                    print("Successfully recovered and completed!")
                    return
    except Exception as e:
        print("WebSocket Exception:", e)

if __name__ == "__main__":
    asyncio.run(run_recovery())
