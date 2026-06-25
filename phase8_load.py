import asyncio
import websockets
import json
import urllib.request
import base64
import time
import statistics
import sys

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

async def simulate_student(audio_bytes, idx):
    uri = "ws://127.0.0.1:80/api/v1/voice/stream"
    try:
        async with websockets.connect(uri) as ws:
            await ws.send(json.dumps({
                "type": "session_start",
                "session_id": f"load_{idx}_{int(time.time())}",
                "language": "en"
            }))
            
            # Send entire audio fast to simulate network
            chunk_size = 4096
            for i in range(0, len(audio_bytes), chunk_size):
                chunk = audio_bytes[i:i+chunk_size]
                await ws.send(json.dumps({
                    "type": "audio_chunk",
                    "data": base64.b64encode(chunk).decode('utf-8')
                }))
                await asyncio.sleep(0.001)
                
            start_time = time.perf_counter()
            await ws.send(json.dumps({"type": "audio_complete"}))
            
            while True:
                msg = await asyncio.wait_for(ws.recv(), timeout=30.0)
                if isinstance(msg, bytes):
                    continue
                data = json.loads(msg)
                if data["type"] == "response_complete":
                    latency = (time.perf_counter() - start_time) * 1000
                    return latency
                elif data["type"] == "error":
                    return -1
    except Exception as e:
        return -1

async def run_load_test(audio_bytes, num_students):
    print(f"\n--- Load Testing {num_students} Concurrent Students ---")
    tasks = [simulate_student(audio_bytes, i) for i in range(num_students)]
    results = await asyncio.gather(*tasks)
    
    valid = [r for r in results if r > 0]
    errors = len(results) - len(valid)
    
    print(f"Total: {num_students}, Success: {len(valid)}, Errors: {errors}")
    if valid:
        avg_latency = statistics.mean(valid)
        valid.sort()
        p95_index = int(len(valid) * 0.95) - 1
        p95_latency = valid[max(0, p95_index)]
        print(f"Average Latency: {avg_latency:.2f}ms")
        print(f"P95 Latency: {p95_latency:.2f}ms")
        
async def main():
    audio_bytes = get_audio("Hello tutor, testing concurrency.", "en")
    await run_load_test(audio_bytes, 10)
    await run_load_test(audio_bytes, 50)

if __name__ == "__main__":
    asyncio.run(main())
