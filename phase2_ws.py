import asyncio
import websockets
import json

async def test_websocket():
    uri = "ws://127.0.0.1:8000/api/v1/voice/stream"
    try:
        async with websockets.connect(uri) as ws:
            print("Connected to WebSocket")
            
            # Test 1: Malformed JSON
            await ws.send("this is not json")
            try:
                resp = await asyncio.wait_for(ws.recv(), timeout=2.0)
                print("Test 1 response:", resp)
            except Exception as e:
                print("Test 1 error:", e)

            # Test 2: Invalid event type
            await ws.send(json.dumps({"type": "bogus_event"}))
            try:
                resp = await asyncio.wait_for(ws.recv(), timeout=2.0)
                print("Test 2 response:", resp)
            except Exception as e:
                print("Test 2 error:", e)

            # Test 3: Audio chunk before audio_start
            await ws.send(json.dumps({"type": "audio_chunk", "audio": "base64data=="}))
            try:
                resp = await asyncio.wait_for(ws.recv(), timeout=2.0)
                print("Test 3 response:", resp)
            except Exception as e:
                print("Test 3 error:", e)

    except Exception as e:
        print("Connection failed:", e)

asyncio.run(test_websocket())
