import urllib.request
import json

payload = {
    "pack_type": "chapter",
    "grade": 10,
    "subject": "science",
    "chapter": "electricity",
    "language": "english",
    "include_media": False,
    "compression": "gzip",
    "quantize_embeddings": False,
}

req = urllib.request.Request(
    'http://127.0.0.1:80/packs/generate',
    data=json.dumps(payload).encode('utf-8'),
    headers={'Content-Type': 'application/json'},
    method='POST'
)

print("Requesting...")
with urllib.request.urlopen(req, timeout=300) as f:
    print(f.status, f.read().decode('utf-8'))
