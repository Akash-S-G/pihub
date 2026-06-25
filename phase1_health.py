import urllib.request
import time
import json
import socket

services = {
    "gateway": "http://gateway:8000/health",
    "voice-service": "http://voice-service:8050/health",
    "inference-service": "http://inference-service:8010/health",
    "content-pipeline": "http://content-pipeline:8001/health",
    "pack-service": "http://pack-service:8030/health",
    "pihub": "http://pihub:8020/health"
}

results = []
all_passed = True

for name, url in services.items():
    try:
        start = time.time()
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            latency = int((time.time() - start) * 1000)
            status = data.get("status") == "healthy" or data.get("status") == "ok"
            if not status and "status" not in data:
                status = response.status == 200
            
            results.append({
                "service": name,
                "healthy": status,
                "latency_ms": latency
            })
            if not status:
                all_passed = False
    except Exception as e:
        results.append({
            "service": name,
            "healthy": False,
            "error": str(e),
            "latency_ms": -1
        })
        all_passed = False

print(json.dumps(results, indent=2))
if not all_passed:
    exit(1)
