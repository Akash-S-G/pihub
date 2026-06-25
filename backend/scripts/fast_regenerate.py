import urllib.request
import json
import time
from concurrent.futures import ThreadPoolExecutor

def request_json(url, payload):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as f:
            return f.status, json.loads(f.read().decode('utf-8'))
    except Exception as e:
        return 500, str(e)

def get_sync():
    req = urllib.request.Request('http://127.0.0.1:80/packs/sync')
    with urllib.request.urlopen(req) as f:
        return json.loads(f.read().decode('utf-8'))

sync_data = get_sync()
packs = [p for p in sync_data.get('packs', []) if p.get('grade') in [6, 7, 9, 10]]

print(f"Regenerating {len(packs)} packs...")

def generate(pack):
    payload = {
        "pack_type": "chapter" if pack.get("chapter") else "class",
        "grade": pack.get("grade"),
        "subject": pack.get("subject"),
        "chapter": pack.get("chapter"),
        "language": pack.get("language") or "english",
        "include_media": False,
        "compression": "gzip",
        "quantize_embeddings": False,
    }
    status, _ = request_json('http://127.0.0.1:80/packs/generate', payload)
    print(f"Generated {pack.get('pack_id')} - Status {status}")

with ThreadPoolExecutor(max_workers=2) as executor:
    executor.map(generate, packs)

print("Done!")
