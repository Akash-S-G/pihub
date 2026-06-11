#!/usr/bin/env python3
import urllib.request
import urllib.error
import json
import sys

# Test via the public nginx port for gateway
GATEWAY_URL = "http://localhost:80"
# Fallback to direct container for internal-only routes
PACK_SERVICE_URL = "http://localhost:8030"

def check_status(response, expected_status=200):
    if response.status != expected_status:
        print(f"FAIL: Expected status {expected_status}, got {response.status}")
        sys.exit(1)

def test_health():
    print("Testing /health...")
    req = urllib.request.Request(f"{GATEWAY_URL}/health")
    with urllib.request.urlopen(req) as response:
        check_status(response)
        data = json.loads(response.read().decode())
        assert "status" in data
        assert data["status"] in ["ok", "degraded"]
    print("OK")

def test_pack_listing():
    print("Testing /packs listing...")
    req = urllib.request.Request(f"{GATEWAY_URL}/packs")
    with urllib.request.urlopen(req) as response:
        check_status(response)
        data = json.loads(response.read().decode())
        assert "packs" in data
        assert isinstance(data["packs"], list)
        if len(data["packs"]) > 0:
            pack = data["packs"][0]
            assert "pack_id" in pack
            assert "manifest_url" in pack
            assert "download_url" in pack
            return pack["pack_id"]
    return None

def test_rag_search():
    print("Testing /rag/search...")
    payload = json.dumps({"query": "maths", "limit": 2}).encode("utf-8")
    req = urllib.request.Request(f"{GATEWAY_URL}/rag/search", data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as response:
        check_status(response)
        data = json.loads(response.read().decode())
        assert "results" in data
        assert isinstance(data["results"], list)
    print("OK")

def test_tutor():
    print("Testing /ai/tutor...")
    payload = json.dumps({"question": "What is 2+2?", "limit": 1}).encode("utf-8")
    req = urllib.request.Request(f"{GATEWAY_URL}/ai/tutor", data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as response:
            check_status(response)
            data = json.loads(response.read().decode())
            assert "answer" in data
            assert "context" in data
        print("OK")
    except urllib.error.HTTPError as e:
        print(f"FAIL: Tutor failed with {e.code} {e.reason}")
        sys.exit(1)

if __name__ == "__main__":
    test_health()
    pack_id = test_pack_listing()
    test_rag_search()
    test_tutor()
    print("ALL INTEGRATION TESTS PASSED.")
